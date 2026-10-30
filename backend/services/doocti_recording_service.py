import datetime
import json
import logging
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

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
        Finds the ONE recording that belongs to a call that was never finalised by a
        CDR (browser closed, hangup message lost, webhook never delivered).

        Recording keys are named after the PBX uniqueid, whose epoch is the call start
        time, so a narrow window around ``started_at`` is a reliable join. Only a
        single, unused candidate is ever claimed: if the window is ambiguous nothing
        is linked rather than attaching somebody else's audio.
        """
        base_url = (base_url or cls.get_configured_base_url(db)).rstrip("/")
        target_dt = call.started_at or call.created_at
        if not isinstance(target_dt, datetime.datetime):
            return None
        if target_dt.tzinfo:
            target_dt = target_dt.astimezone(IST_TIMEZONE).replace(tzinfo=None)

        dates = [target_dt.strftime("%Y-%m-%d")]
        if target_dt.hour == 0 and target_dt.minute < 15:
            dates.append((target_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d"))

        candidates: List[Dict[str, Any]] = []
        for d in dates:
            for cand in cls.fetch_bucket_recordings_for_date(d, base_url):
                if cand.get("size", 0) < 500:
                    continue
                cand_dt = cand.get("dt_ist")
                if not cand_dt:
                    continue
                diff = (cand_dt - target_dt).total_seconds()
                if -window_before <= diff <= window_after:
                    candidates.append(cand)

        if len(candidates) != 1:
            return None

        cand = candidates[0]
        cand_url = cand.get("url")
        cand_uid = cand.get("uniqueid")
        cand_dt = cand.get("dt_ist")
        if not cand_url:
            return None

        # If another call session started at almost the same moment, the audio cannot
        # be attributed unambiguously - leave it unlinked rather than guessing.
        if cand_dt:
            sibling = (
                db.query(CallLog.id)
                .filter(
                    CallLog.id != call.id,
                    or_(
                        and_(
                            CallLog.started_at.isnot(None),
                            CallLog.started_at >= cand_dt - datetime.timedelta(seconds=window_before),
                            CallLog.started_at <= cand_dt + datetime.timedelta(seconds=window_after),
                        ),
                        and_(
                            CallLog.started_at.is_(None),
                            CallLog.created_at >= cand_dt - datetime.timedelta(seconds=window_before),
                            CallLog.created_at <= cand_dt + datetime.timedelta(seconds=window_after),
                        ),
                    ),
                )
                .first()
            )
            if sibling:
                return None

        # Never steal a recording that is already attached to another call.
        used_url = (
            db.query(CallLog.id)
            .filter(CallLog.recording_url == cand_url, CallLog.id != call.id)
            .first()
        )
        if used_url:
            return None
        if cand_uid:
            used_uid = (
                db.query(CallLog.id)
                .filter(CallLog.provider_call_id == cand_uid, CallLog.id != call.id)
                .first()
            )
            if used_uid:
                return None

        if not cls.url_exists(cand_url):
            return None
        return cand_url

    @classmethod
    def match_recording_for_call(
        cls,
        call: CallLog,
        db: Session,
        base_url: Optional[str] = None,
        auto_save: bool = True
    ) -> Optional[str]:
        """
        Resolves or matches the audio recording URL for a CallLog instance.
        If recording is found, updates call.recording_url, links real Asterisk uniqueid,
        and persists to DB if auto_save is True.
        """
        # 1. Existing valid public recording URL
        curr_rec = str(call.recording_url or "").strip()
        if curr_rec and "127.0.0.1" not in curr_rec and "localhost" not in curr_rec:
            return curr_rec

        # 2. Existing loopback URL (127.0.0.1/audio/...) -> normalize to Oracle Cloud storage
        target_base = (base_url or cls.get_configured_base_url(db)).rstrip("/")
        if curr_rec and ("127.0.0.1" in curr_rec or "localhost" in curr_rec):
            match = re.search(r"https?://[^/]+(?:/audio)?(/.*)", curr_rec)
            if match:
                path = match.group(1)
                if path.endswith(".wav"):
                    path = path[:-4] + ".mp3"
                resolved = f"{target_base}{path}"
                # Only keep the rewrite when the object really exists; otherwise
                # fall through to the bucket listing which can find the right key.
                if cls.url_exists(resolved):
                    call.recording_url = resolved
                    if auto_save:
                        try:
                            db.commit()
                        except Exception:
                            db.rollback()
                    return resolved

        # 3. Only attempt bucket resolution for calls that were connected / completed or have positive duration
        st_upper = (call.call_status or "").upper()
        is_candidate = (
            (call.duration_seconds is not None and call.duration_seconds > 0)
            or st_upper in ["COMPLETED", "COMPLETE", "ANSWERED", "CONNECTED"]
        )
        if not is_candidate:
            return None

        # 4. If provider_call_id is a native Asterisk uniqueid (e.g. 1793333301.131253490)
        prov_id = str(call.provider_call_id or "").strip()
        is_asterisk_uid = bool(re.match(r"^\d{9,11}\.\d+$", prov_id))
        target_dt = call.started_at or call.created_at or get_ist_now()
        date_str = target_dt.strftime("%Y-%m-%d")

        if is_asterisk_uid:
            direct_url = f"{target_base}/{date_str}/{prov_id}.mp3"
            # Only persist the direct URL when the object really exists; otherwise
            # fall through to the bucket listing (Asterisk may name the file with
            # the answered leg's uniqueid instead of the caller leg's).
            if cls.url_exists(direct_url):
                call.recording_url = direct_url
                if auto_save:
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
                return direct_url

        # 5. Search Oracle Object Storage bucket for the call date
        dates_to_search = [date_str]
        # If call occurred within 30 minutes of midnight, also check previous or next day
        if target_dt.hour == 0 and target_dt.minute < 30:
            prev_day = (target_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            dates_to_search.append(prev_day)
        elif target_dt.hour == 23 and target_dt.minute > 30:
            next_day = (target_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            dates_to_search.append(next_day)

        recordings: List[Dict[str, Any]] = []
        for d in dates_to_search:
            recordings.extend(cls.fetch_bucket_recordings_for_date(d, target_base))

        if not recordings:
            return None

        # Matching algorithm:
        # Candidate must:
        # - Have audio data (size > 500 bytes to filter empty 144B headers)
        # - Fall within a ±15-minute window of the call start/connect time
        expected_size = max(5000, (call.duration_seconds or 10) * 1000)
        best_candidate: Optional[Dict[str, Any]] = None
        best_score = float("inf")

        # An exact filename/uniqueid match is authoritative - use it directly.
        if prov_id:
            for cand in recordings:
                if cand.get("uniqueid") == prov_id and cand.get("size", 0) >= 500:
                    best_candidate = cand
                    best_score = 0.0
                    break

        if not best_candidate:
            for cand in recordings:
                if cand["size"] < 500:
                    continue
                cand_dt = cand.get("dt_ist")
                if not cand_dt:
                    continue

                time_diff = abs((cand_dt - target_dt).total_seconds())
                if time_diff > 900:  # 15 minutes max difference
                    continue

                # Weight score by time proximity and audio size correlation
                size_diff = abs(cand["size"] - expected_size)
                score = time_diff + (size_diff / 800.0)

                if score < best_score:
                    best_score = score
                    best_candidate = cand

        if best_candidate:
            matched_url = best_candidate["url"]
            call.recording_url = matched_url

            # If call had a synthetic ID (doocti_1282_...), update with real Asterisk PBX uniqueid if unique
            uid_cand = best_candidate.get("uniqueid")
            if uid_cand and (prov_id.startswith("doocti_") or not prov_id):
                conflict = (
                    db.query(CallLog)
                    .filter(CallLog.provider_call_id == uid_cand, CallLog.id != call.id)
                    .first()
                )
                if not conflict:
                    call.provider_call_id = uid_cand

            if auto_save:
                call_id_val = call.id
                try:
                    db.commit()
                    logger.info(
                        f"🎯 [DooctiRecording] Auto-linked recording for Call ID={call_id_val}: "
                        f"{best_candidate['filename']} (Size={best_candidate['size']}B, Diff={best_score:.1f})"
                    )
                except Exception as save_err:
                    db.rollback()
                    logger.warning(f"Failed to save matched recording URL to CallLog ID={call_id_val}: {save_err}")

            return matched_url

        return None

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

