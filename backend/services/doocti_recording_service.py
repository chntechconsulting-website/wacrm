import datetime
import json
import logging
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func

from models.call_log import CallLog
from models.integration import IntegrationConfig
from utils.timezone import get_ist_now, IST_TIMEZONE

logger = logging.getLogger("wacrm.doocti_recording")

DEFAULT_RECORDING_BASE_URL = (
    "https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009"
)

# In-memory bucket listing cache: { "date_str": (timestamp, [recordings]) }
_BUCKET_LISTING_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
CACHE_TTL_SECONDS = 30.0  # short TTL so freshly uploaded recordings are picked up quickly

# In-memory URL existence cache: { "url": (timestamp, exists) }
_URL_EXISTS_CACHE: Dict[str, Tuple[float, bool]] = {}
URL_EXISTS_TTL_SECONDS = 45.0

# In-memory audio duration cache: { "url": (timestamp, duration_seconds|None) }
_AUDIO_DURATION_CACHE: Dict[str, Tuple[float, Optional[int]]] = {}
AUDIO_DURATION_TTL_SECONDS = 3600.0

# Webhook fields that identify the recording artifact itself. A recording may be
# named after the answered leg, so this identity is stored separately from the
# call uniqueid (but is still never guessed).
RECORDING_ID_KEYS = (
    "recording_id", "recording_uniqueid", "recording_unique_id",
    "recording_name", "recording_file", "recording_filename", "rec_file",
)
RECORDING_DURATION_KEYS = (
    "recording_duration", "recording_duration_seconds", "rec_duration",
    "record_duration", "audio_duration",
)


def extract_recording_metadata(
    raw_data: Dict[str, Any], rec_url: Optional[str]
) -> Tuple[Optional[str], Optional[int]]:
    """Returns (recording_id, recording_duration_seconds) from a webhook payload."""
    recording_id = None
    for key in RECORDING_ID_KEYS:
        value = raw_data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and not text.startswith("%") and not text.startswith("$"):
            recording_id = text
            break
    if recording_id and ("/" in recording_id or "\\" in recording_id):
        recording_id = DooctiRecordingService.recording_id_from_url(recording_id)
    if not recording_id and rec_url:
        recording_id = DooctiRecordingService.recording_id_from_url(rec_url)

    duration = None
    for key in RECORDING_DURATION_KEYS:
        value = raw_data.get(key)
        if value is None or value == "":
            continue
        try:
            parsed = int(float(str(value).strip()))
        except (TypeError, ValueError):
            continue
        if 0 <= parsed <= 24 * 60 * 60:
            duration = parsed
            break

    return recording_id, duration


# MPEG audio Layer III bitrate tables (kbit/s), indexed by the 4-bit bitrate index.
_MPEG_LAYER3_BITRATES = {
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],   # MPEG 1
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],       # MPEG 2
    25: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],      # MPEG 2.5
}


class DooctiRecordingService:
    """
    Automated resolver and synchronizer for DooCTI telephony call recordings.
    Resolves recordings stored in Oracle Cloud Object Storage, parses S3-compatible XML listings,
    and accurately correlates missing recordings with CallLog records by Asterisk PBX unique ID,
    timestamp, and audio duration.
    """

    @classmethod
    def get_configured_base_url(cls, db: Session) -> str:
        """Retrieves authoritative recording base URL from IntegrationConfig or default."""
        try:
            cfg = db.query(IntegrationConfig).filter(IntegrationConfig.integration_type == "IVR").first()
            if cfg and cfg.config_data:
                data = json.loads(cfg.config_data or "{}")
                base = data.get("recording_base_url") or data.get("media_url")
                if base and str(base).strip() and "beta3-app.doocti.com" not in base:
                    return str(base).strip().rstrip("/")
        except Exception as e:
            logger.debug(f"[DooctiRecording] Could not read recording_base_url from DB: {e}")
        return DEFAULT_RECORDING_BASE_URL.rstrip("/")

    @classmethod
    def parse_storage_endpoints(cls, base_url: str) -> Tuple[str, str, str]:
        """
        Parses an Oracle Cloud Storage base URL into (list_query_url, base_object_url, prefix).
        Example:
          base_url = 'https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009'
          Returns:
            list_url: 'https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti'
            base_object_url: 'https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti/cti_chntechnolog_20261009'
            prefix: 'cti_chntechnolog_20261009'
        """
        clean = base_url.strip().rstrip("/")
        match = re.match(r"(https?://[^/]+/[^/]+)/(.+)", clean)
        if match:
            list_url = match.group(1)
            prefix = match.group(2).strip("/")
            return list_url, clean, prefix

        # Fallback to defaults
        return (
            "https://bmxrx2cviyka.compat.objectstorage.ap-mumbai-1.oraclecloud.com/doocti",
            DEFAULT_RECORDING_BASE_URL.rstrip("/"),
            "cti_chntechnolog_20261009",
        )

    @classmethod
    def fetch_bucket_recordings_for_date(
        cls, date_str: str, base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists audio files stored in Oracle Cloud storage under prefix/{date_str}/.
        Returns parsed list of recording metadata dictionaries.
        Results are cached in memory for CACHE_TTL_SECONDS.
        """
        now = time.time()
        cached = _BUCKET_LISTING_CACHE.get(date_str)
        if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        target_base = (base_url or DEFAULT_RECORDING_BASE_URL).rstrip("/")
        list_url, base_object_url, prefix = cls.parse_storage_endpoints(target_base)
        query_url = f"{list_url}?prefix={prefix}/{date_str}/"

        recordings: List[Dict[str, Any]] = []
        try:
            req = urllib.request.Request(
                query_url,
                headers={"User-Agent": "WACRM-RecordingResolver/1.0", "Accept": "application/xml"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            for item in root.findall("s3:Contents", ns):
                key_node = item.find("s3:Key", ns)
                if key_node is None or not key_node.text:
                    continue
                key_text = key_node.text.strip()
                size_node = item.find("s3:Size", ns)
                size_bytes = int(size_node.text.strip()) if size_node is not None and size_node.text else 0
                lm_node = item.find("s3:LastModified", ns)
                last_modified = lm_node.text.strip() if lm_node is not None and lm_node.text else None

                fname = key_text.split("/")[-1]
                if not fname.endswith(".mp3"):
                    continue

                raw_uniqueid = fname[:-4]  # Strip .mp3
                raw_epoch = raw_uniqueid.split(".")[0] if "." in raw_uniqueid else raw_uniqueid

                dt_call: Optional[datetime.datetime] = None
                if raw_epoch.isdigit():
                    try:
                        epoch_val = int(raw_epoch)
                        dt_call = datetime.datetime.fromtimestamp(epoch_val, tz=IST_TIMEZONE).replace(tzinfo=None)
                    except Exception:
                        dt_call = None

                public_url = f"{list_url}/{key_text}"
                recordings.append(
                    {
                        "key": key_text,
                        "filename": fname,
                        "uniqueid": raw_uniqueid,
                        "url": public_url,
                        "size": size_bytes,
                        "last_modified": last_modified,
                        "dt_ist": dt_call,
                    }
                )

            _BUCKET_LISTING_CACHE[date_str] = (now, recordings)
            logger.debug(f"[DooctiRecording] Fetched {len(recordings)} audio files for {date_str}")
        except Exception as e:
            logger.warning(f"[DooctiRecording] Failed to fetch Oracle Cloud bucket list for {date_str}: {e}")
            return []

        return recordings

    @classmethod
    def url_exists(cls, url: str, min_size: int = 500) -> bool:
        """
        Verifies that a recording object actually exists (and is not an empty stub)
        before we persist it on a CallLog. Prevents dead "0:00 / 0:00" players.
        """
        now = time.time()
        cached = _URL_EXISTS_CACHE.get(url)
        if cached and (now - cached[0]) < URL_EXISTS_TTL_SECONDS:
            return cached[1]

        exists = False
        headers = {"User-Agent": "WACRM-RecordingResolver/1.0"}
        try:
            req = urllib.request.Request(url, headers=headers, method="HEAD")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                length = int(resp.headers.get("Content-Length") or 0)
                exists = 200 <= int(getattr(resp, "status", 200)) < 300 and length >= min_size
        except Exception:
            # Some object stores reject HEAD; retry with a 1-byte ranged GET.
            try:
                ranged_headers = dict(headers)
                ranged_headers["Range"] = "bytes=0-0"
                req = urllib.request.Request(url, headers=ranged_headers)
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    length = int(resp.headers.get("Content-Range", "").split("/")[-1] or 0)
                    exists = 200 <= int(getattr(resp, "status", 200)) < 300 and length >= min_size
            except Exception:
                exists = False

        _URL_EXISTS_CACHE[url] = (now, exists)
        return exists

    @classmethod
    def _parse_mpeg_duration(cls, header: bytes, total_size: int) -> Optional[int]:
        """
        Derives the playback length of an MPEG audio file from its first frame header
        plus the object size. DooCTI recordings carry no Xing/VBRI duration header, so
        the frame header (bitrate + sample rate) is the authoritative source:
            duration = (audio_bytes * 8) / bitrate_bps
        Returns an integer number of seconds, or None when the data is not MPEG audio.
        """
        if not header or total_size <= 0:
            return None

        start = -1
        for i in range(0, max(0, len(header) - 3)):
            if header[i] == 0xFF and (header[i + 1] & 0xE0) == 0xE0:
                start = i
                break
        if start < 0:
            return None

        b1 = header[start + 1]
        b2 = header[start + 2]
        version_bits = (b1 >> 3) & 0x03
        layer_bits = (b1 >> 1) & 0x03
        bitrate_idx = (b2 >> 4) & 0x0F
        sample_idx = (b2 >> 2) & 0x03

        # Layer III only (recording files are MP3). 0b01 == Layer III.
        if layer_bits != 0x01:
            return None
        if version_bits == 0x03:
            version = 1
        elif version_bits == 0x02:
            version = 2
        elif version_bits == 0x00:
            version = 25
        else:
            return None
        if bitrate_idx in (0, 15) or sample_idx == 3:
            return None

        bitrate_kbps = _MPEG_LAYER3_BITRATES[version][bitrate_idx]
        if not bitrate_kbps:
            return None

        audio_bytes = max(0, int(total_size) - start)
        seconds = (audio_bytes * 8.0) / (bitrate_kbps * 1000.0)
        if seconds <= 0:
            return None
        return int(round(seconds))

    @classmethod
    def resolve_audio_duration(cls, url: Optional[str], timeout: float = 6.0) -> Optional[int]:
        """
        Returns the real duration (seconds) of a recording object.
        Uses a HEAD request for the exact object size and a 4 KB ranged GET for the
        first MPEG frame header. Results are cached in memory.
        """
        clean_url = str(url or "").strip()
        if not clean_url:
            return None

        now = time.time()
        cached = _AUDIO_DURATION_CACHE.get(clean_url)
        if cached and (now - cached[0]) < AUDIO_DURATION_TTL_SECONDS:
            return cached[1]

        duration: Optional[int] = None
        headers = {"User-Agent": "WACRM-RecordingResolver/1.0"}
        try:
            total_size = 0
            try:
                req = urllib.request.Request(clean_url, headers=headers, method="HEAD")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    total_size = int(resp.headers.get("Content-Length") or 0)
            except Exception:
                total_size = 0

            ranged = dict(headers)
            ranged["Range"] = "bytes=0-4095"
            req = urllib.request.Request(clean_url, headers=ranged)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                head_bytes = resp.read(4096)
                if not total_size:
                    content_range = resp.headers.get("Content-Range") or ""
                    if "/" in content_range:
                        try:
                            total_size = int(content_range.rsplit("/", 1)[-1])
                        except ValueError:
                            total_size = 0
                if not total_size:
                    total_size = int(resp.headers.get("Content-Length") or 0)

            if total_size >= 500:
                duration = cls._parse_mpeg_duration(head_bytes, total_size)
        except Exception as exc:
            logger.debug(f"[DooctiRecording] Could not resolve audio duration for {clean_url}: {exc}")
            duration = None

        _AUDIO_DURATION_CACHE[clean_url] = (now, duration)
        return duration

    # ------------------------------------------------------------------
    # Exact recording identity helpers
    # ------------------------------------------------------------------

    # Asterisk/FreePBX uniqueids look like "1793333301.131253490". Only these
    # (or equally authoritative numeric provider call ids) may be used to join
    # a recording to a call.
    _AUTHORITATIVE_ID_RE = re.compile(r"^\d{9,13}(?:\.\d+)?$")
    _SYNTHETIC_PREFIXES = ("DOOCTI_", "CALL_", "SIM_", "CS_CALL_", "SMARTFLO_CALL_")
    _RECORDING_EXTENSIONS = (
        ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".amr",
        ".3gp", ".caf", ".webm", ".mp4",
    )

    @classmethod
    def is_authoritative_call_id(cls, value: Any) -> bool:
        """True only for IDs the PBX itself generated (never CRM synthetic ids)."""
        clean = str(value or "").strip()
        if not clean:
            return False
        if clean.upper().startswith(cls._SYNTHETIC_PREFIXES):
            return False
        return bool(cls._AUTHORITATIVE_ID_RE.match(clean))

    @classmethod
    def recording_id_from_url(cls, url: Optional[str]) -> Optional[str]:
        """Extracts the recording's own uniqueid from its filename."""
        clean = str(url or "").strip()
        if not clean:
            return None
        path = clean.split("?", 1)[0].split("#", 1)[0].rstrip("/\\")
        name = re.split(r"[\\/]", path)[-1]
        low = name.lower()
        for ext in cls._RECORDING_EXTENSIONS:
            if low.endswith(ext):
                name = name[: -len(ext)]
                break
        return name.strip() or None

    @classmethod
    def _recording_belongs_to_call(cls, call: CallLog, url: Optional[str], db: Session) -> bool:
        """
        Rejects a URL that provably belongs to another call row.

        Legacy rows were sometimes given a recording whose filename is the
        *other* call's PBX uniqueid. That is proof of a wrong association: the
        call that owns that uniqueid is the only legal owner.
        """
        rec_id = cls.recording_id_from_url(url)
        if not rec_id or not cls.is_authoritative_call_id(rec_id):
            return True
        if str(call.provider_call_id or "").strip() == rec_id:
            return True
        try:
            owner = (
                db.query(CallLog.id)
                .filter(CallLog.provider_call_id == rec_id, CallLog.id != call.id)
                .first()
            )
        except Exception:
            return True
        if owner:
            return False
        stored_id = str(call.recording_id or "").strip()
        if stored_id and cls.is_authoritative_call_id(stored_id) and stored_id != rec_id:
            return False
        return True

    @classmethod
    def _recording_date_for_id(cls, uniqueid: str, fallback_dt: datetime.datetime) -> str:
        """Bucket folders are IST dates derived from the uniqueid's epoch."""
        match = re.match(r"^(\d{9,13})(?:\.\d+)?$", uniqueid or "")
        if match:
            try:
                epoch = int(match.group(1))
                dt_ist = datetime.datetime.fromtimestamp(epoch, tz=IST_TIMEZONE)
                return dt_ist.strftime("%Y-%m-%d")
            except (ValueError, OSError, OverflowError):
                pass
        return fallback_dt.strftime("%Y-%m-%d")

    @classmethod
    def _find_exact_bucket_recording(
        cls,
        call: CallLog,
        db: Session,
        base_url: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the bucket object whose filename is exactly the call's
        provider uniqueid. No time/size scoring is performed.
        """
        prov_id = str(call.provider_call_id or "").strip()
        if not cls.is_authoritative_call_id(prov_id):
            return None
        target_dt = call.started_at or call.created_at or get_ist_now()
        if isinstance(target_dt, datetime.datetime) and target_dt.tzinfo:
            target_dt = target_dt.astimezone(IST_TIMEZONE).replace(tzinfo=None)
        if not isinstance(target_dt, datetime.datetime):
            target_dt = get_ist_now()

        date_str = cls._recording_date_for_id(prov_id, target_dt)
        direct_url = f"{base_url.rstrip('/')}/{date_str}/{prov_id}.mp3"
        if cls.url_exists(direct_url):
            return {
                "uniqueid": prov_id,
                "url": direct_url,
                "filename": f"{prov_id}.mp3",
                "size": 0,
            }

        # The folder date is normally encoded in the uniqueid. Check the
        # neighbouring IST dates only as an exact-name lookup.
        dates = [date_str]
        epoch_match = re.match(r"^(\d{9,13})", prov_id)
        if epoch_match:
            try:
                epoch_dt = datetime.datetime.fromtimestamp(
                    int(epoch_match.group(1)), tz=IST_TIMEZONE
                )
                dates = [
                    (epoch_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                    epoch_dt.strftime("%Y-%m-%d"),
                    (epoch_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                ]
            except (ValueError, OSError, OverflowError):
                pass

        for d in dates:
            for cand in cls.fetch_bucket_recordings_for_date(d, base_url):
                if str(cand.get("uniqueid") or "").strip() != prov_id:
                    continue
                if int(cand.get("size") or 0) < 500:
                    continue
                if not cls.url_exists(cand.get("url")):
                    continue
                return cand
        return None

    @classmethod
    def attach_recording(
        cls,
        call: CallLog,
        db: Session,
        url: Optional[str],
        recording_id: Optional[str] = None,
        duration: Optional[int] = None,
        source: Optional[str] = None,
        commit: bool = True,
        derive_duration: bool = False,
    ) -> bool:
        """
        Links a recording to exactly one call, with duplicate protection.

        The recording is expected to carry its own identity (uniqueid in the
        filename or an explicit recording id from the webhook). If the same
        recording is already stored on another call the link is refused rather
        than duplicated.
        """
        clean_url = str(url or "").strip()
        if not clean_url:
            return False
        rec_id = str(recording_id or "").strip() or cls.recording_id_from_url(clean_url)

        try:
            if rec_id:
                conflict = (
                    db.query(CallLog.id)
                    .filter(CallLog.id != call.id, CallLog.recording_id == rec_id)
                    .first()
                )
                if conflict:
                    logger.warning(
                        f"[DooctiRecording] Refusing duplicate recording id '{rec_id}' "
                        f"for Call ID={call.id}; already linked to Call ID={conflict[0]}."
                    )
                    return False
            conflict_url = (
                db.query(CallLog.id)
                .filter(CallLog.id != call.id, CallLog.recording_url == clean_url)
                .first()
            )
            if conflict_url:
                logger.warning(
                    f"[DooctiRecording] Refusing duplicate recording URL for Call ID={call.id}; "
                    f"already linked to Call ID={conflict_url[0]}."
                )
                return False
        except Exception as exc:
            logger.debug(f"[DooctiRecording] Duplicate check failed for Call ID={call.id}: {exc}")

        if duration is None and derive_duration:
            duration = cls.resolve_audio_duration(clean_url)

        call.recording_url = clean_url
        if rec_id:
            call.recording_id = rec_id
        if duration is not None:
            try:
                call.recording_duration_seconds = int(duration)
            except (TypeError, ValueError):
                pass
        call.recording_source = source or call.recording_source or "DOOCTI"
        call.recording_attached_at = get_ist_now()

        if commit:
            try:
                db.commit()
            except Exception as save_err:
                db.rollback()
                logger.warning(
                    f"[DooctiRecording] Failed to save recording for Call ID={call.id}: {save_err}"
                )
                return False
        return True

    @classmethod
    def repair_misassigned_recordings(cls, db: Session, limit: int = 500) -> int:
        """
        Non-destructive repair for legacy rows whose recording filename is the
        uniqueid of a *different* call row. The link is moved to its rightful
        owner (or cleared when the owner already has audio). Files and call logs
        are never deleted.
        """
        repaired = 0
        calls = (
            db.query(CallLog)
            .filter(CallLog.recording_url.isnot(None))
            .order_by(desc(CallLog.id))
            .limit(limit)
            .all()
        )
        for call in calls:
            rec_id = cls.recording_id_from_url(call.recording_url)
            if not rec_id or not cls.is_authoritative_call_id(rec_id):
                continue
            if str(call.provider_call_id or "").strip() == rec_id:
                continue
            owner = (
                db.query(CallLog)
                .filter(CallLog.provider_call_id == rec_id, CallLog.id != call.id)
                .first()
            )
            if not owner:
                continue
            if not owner.recording_url and not owner.recording_id:
                owner.recording_url = call.recording_url
                owner.recording_id = rec_id
                owner.recording_duration_seconds = call.recording_duration_seconds
                owner.recording_source = call.recording_source or "DOOCTI"
                owner.recording_attached_at = call.recording_attached_at
                logger.info(
                    f"[DooctiRecording] Moved legacy recording '{rec_id}' from "
                    f"Call ID={call.id} to its owner Call ID={owner.id}."
                )
            call.recording_url = None
            call.recording_id = None
            call.recording_duration_seconds = None
            call.recording_attached_at = None
            repaired += 1
        if repaired:
            try:
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning(f"[DooctiRecording] Legacy recording repair failed: {exc}")
                return 0
        return repaired

    @classmethod
    def claim_unambiguous_recording(
        cls,
        call: CallLog,
        db: Session,
        base_url: Optional[str] = None,
        window_before: int = 90,
        window_after: int = 180,
    ) -> Optional[str]:
        """
        Links a recording only when the call's own authoritative uniqueid matches
        a stored recording. Time-window guessing was removed: a missing recording
        is always safer than another customer's audio.
        """
        if str(call.provider or "").upper() in ("MOBILE_SIM", "DIRECT_DIAL"):
            return None
        if not cls.is_authoritative_call_id(call.provider_call_id):
            return None
        return cls.match_recording_for_call(
            call, db, base_url=base_url, auto_save=True
        )

    @classmethod
    def match_recording_for_call(
        cls,
        call: CallLog,
        db: Session,
        base_url: Optional[str] = None,
        auto_save: bool = True
    ) -> Optional[str]:
        """
        Resolves a recording strictly by the call's provider uniqueid.

        There is deliberately no fallback that scores candidates by timestamp or
        file size: that is what previously attached one call's audio to another.
        """
        curr_rec = str(call.recording_url or "").strip()

        # Mobile SIM / direct-dial calls are recorded, if at all, by the device's
        # own dialer and uploaded as an authorised file. They must never be
        # matched against the DooCTI Oracle bucket.
        provider_upper = str(call.provider or "").upper()
        if provider_upper in ("MOBILE_SIM", "DIRECT_DIAL"):
            return None

        # 1. Existing public URL, but never one that provably belongs to another call.
        if curr_rec and "127.0.0.1" not in curr_rec and "localhost" not in curr_rec:
            if cls._recording_belongs_to_call(call, curr_rec, db):
                return curr_rec
            logger.warning(
                f"[DooctiRecording] Ignoring recording on Call ID={call.id}: "
                f"'{curr_rec}' belongs to another call uniqueid."
            )
            return None

        target_base = (base_url or cls.get_configured_base_url(db)).rstrip("/")

        # 2. Loopback URL -> Oracle Cloud object (same uniqueid, no guessing).
        if curr_rec and ("127.0.0.1" in curr_rec or "localhost" in curr_rec):
            match = re.search(r"https?://[^/]+(?:/audio)?(/.*)", curr_rec)
            if match:
                path = match.group(1)
                if path.endswith(".wav"):
                    path = path[:-4] + ".mp3"
                resolved = f"{target_base}{path}"
                if (
                    cls.url_exists(resolved)
                    and cls._recording_belongs_to_call(call, resolved, db)
                ):
                    if auto_save:
                        cls.attach_recording(
                            call, db, resolved, source="DOOCTI", commit=True
                        )
                    return resolved

        # 3. Only connected/completed calls may be resolved automatically.
        st_upper = (call.call_status or "").upper()
        is_candidate = (
            (call.duration_seconds is not None and call.duration_seconds > 0)
            or st_upper in ["COMPLETED", "COMPLETE", "ANSWERED", "CONNECTED"]
        )
        if not is_candidate:
            return None

        # 4. Strict exact-uniqueid lookup.
        if not cls.is_authoritative_call_id(call.provider_call_id):
            return None

        cand = cls._find_exact_bucket_recording(call, db, target_base)
        if not cand:
            return None

        matched_url = cand["url"]
        if not cls._recording_belongs_to_call(call, matched_url, db):
            return None

        if auto_save:
            cls.attach_recording(
                call,
                db,
                matched_url,
                recording_id=str(cand.get("uniqueid") or ""),
                source="DOOCTI",
                commit=True,
            )
            logger.info(
                f"🎯 [DooctiRecording] Linked exact recording for Call ID={call.id} "
                f"uniqueid='{call.provider_call_id}'."
            )
        return matched_url

    @classmethod
    def sync_all_missing_recordings(
        cls,
        db: Session,
        days_back: int = 7,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Scans all recent completed calls missing audio recordings and auto-links them.
        """
        now_ist = get_ist_now()
        since_date = now_ist - datetime.timedelta(days=days_back)
        base_url = cls.get_configured_base_url(db)

        # First correct any provably wrong legacy association (moves/clears the
        # link only; audio files and call logs are never deleted).
        repaired = cls.repair_misassigned_recordings(db)

        calls = (
            db.query(CallLog)
            .filter(
                or_(
                    CallLog.recording_url.is_(None),
                    CallLog.recording_url.ilike("%127.0.0.1%"),
                    CallLog.recording_url.ilike("%localhost%"),
                ),
                CallLog.created_at >= since_date,
                or_(
                    CallLog.duration_seconds > 0,
                    CallLog.call_status.in_(["COMPLETED", "COMPLETE", "ANSWERED", "CONNECTED"]),
                ),
                # Mobile SIM calls never have DooCTI bucket recordings.
                or_(
                    CallLog.provider.is_(None),
                    func.upper(CallLog.provider).notin_(["MOBILE_SIM", "DIRECT_DIAL"]),
                ),
            )
            .order_by(desc(CallLog.id))
            .limit(limit)
            .all()
        )

        matched_count = 0
        updated_calls = []

        for call in calls:
            resolved = cls.match_recording_for_call(call, db, base_url=base_url, auto_save=True)
            if resolved:
                matched_count += 1
                updated_calls.append(
                    {
                        "call_id": call.id,
                        "phone": call.to_number or call.from_number,
                        "direction": call.call_direction,
                        "duration": call.duration_seconds,
                        "recording_url": resolved,
                        "provider_call_id": call.provider_call_id,
                    }
                )

        return {
            "status": "success",
            "synced_count": matched_count,
            "repaired_count": repaired,
            "total_inspected": len(calls),
            "updated_calls": updated_calls,
        }

    @classmethod
    def sync_recent_missing_recordings(
        cls,
        db: Session,
        minutes_back: int = 60,
        limit: int = 25,
    ) -> int:
        """
        Links recordings for calls that finished recently. Intended to run from
        the background scheduler so recordings appear without the user having to
        refresh the Call Logs page several times.
        """
        since = get_ist_now() - datetime.timedelta(minutes=minutes_back)
        base_url = cls.get_configured_base_url(db)

        calls = (
            db.query(CallLog)
            .filter(
                or_(
                    CallLog.recording_url.is_(None),
                    CallLog.recording_url.ilike("%127.0.0.1%"),
                    CallLog.recording_url.ilike("%localhost%"),
                ),
                CallLog.ended_at.isnot(None),
                or_(CallLog.created_at >= since, CallLog.ended_at >= since),
                or_(
                    CallLog.duration_seconds > 0,
                    CallLog.call_status.in_(["COMPLETED", "COMPLETE", "ANSWERED", "CONNECTED"]),
                ),
                # Mobile SIM calls never have DooCTI bucket recordings.
                or_(
                    CallLog.provider.is_(None),
                    func.upper(CallLog.provider).notin_(["MOBILE_SIM", "DIRECT_DIAL"]),
                ),
            )
            .order_by(desc(CallLog.id))
            .limit(limit)
            .all()
        )

        matched_count = 0
        for call in calls:
            try:
                if cls.match_recording_for_call(call, db, base_url=base_url, auto_save=True):
                    matched_count += 1
            except Exception as exc:
                logger.warning(
                    f"[DooctiRecording] Background match failed for Call ID={call.id}: {exc}"
                )
                try:
                    db.rollback()
                except Exception:
                    pass

        if matched_count:
            logger.info(
                f"🎯 [DooctiRecording] Background sync linked {matched_count} "
                f"recording(s) out of {len(calls)} recent call(s)."
            )
        return matched_count


def _run_recent_recording_sync(minutes_back: int) -> int:
    """Runs one scheduler iteration with its own short-lived DB session."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        return DooctiRecordingService.sync_recent_missing_recordings(
            db, minutes_back=minutes_back
        )
    finally:
        db.close()


async def start_recording_sync_scheduler(interval_seconds: int = 20, minutes_back: int = 60):
    """
    Periodically auto-links DooCTI recordings for recently completed calls.
    Runs the blocking HTTP/DB work in a worker thread.
    """
    import asyncio

    logger.info("Call recording auto-link scheduler started.")
    while True:
        try:
            await asyncio.to_thread(_run_recent_recording_sync, minutes_back)
        except Exception as exc:
            logger.warning(f"[DooctiRecording] Scheduler iteration failed: {exc}")
        await asyncio.sleep(interval_seconds)

