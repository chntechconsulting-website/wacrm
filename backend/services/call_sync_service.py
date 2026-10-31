"""
Call session reconciler.

DooCTI's webphone only posts two events to the CRM page: "Ringing" (inbound) and
"hangup". The authoritative outcome of every call is the CDR webhook plus the Oracle
recording artifact. When either of those never reaches the CRM (browser closed,
network drop, webhook outage) a call row can stay stuck in CONNECTING/RINGING forever,
which is exactly what made completed calls disappear from the Call Logs list.

This service closes such orphaned sessions using only real evidence:

* If the call's recording exists in the provider bucket (its key epoch matches the
  session start), the call DID connect. The real duration is derived from the audio
  file and the row becomes COMPLETED with that talk time.
* Otherwise the call is closed as MISSED (inbound) / NO_ANSWER (outbound) with a zero
  duration. No duration, answer time or recording is ever fabricated.

A later, delayed CDR still wins: `push_doocti_call_log` upgrades the row to the
provider's own status/duration when it finally arrives.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, asc, desc, or_

from models.call_log import CallLog
from services.doocti_recording_service import DooctiRecordingService
from utils.timezone import get_ist_now

logger = logging.getLogger("wacrm.call_sync")

ACTIVE_CALL_STATUSES: List[str] = ["RINGING", "CONNECTING", "ANSWERED", "INITIATED", "INITIATING"]

# DooCTI answers/records only when a call is actually connected. A ring that never
# connected never produces audio, so the presence of a recording is proof of answer.
STALE_AFTER_MINUTES = 30


def _finalize_one(db, call: CallLog, dry_run: bool = False) -> Dict[str, Any]:
    started_at = call.started_at or call.created_at or get_ist_now()

    rec_url = (call.recording_url or "").strip() or None
    if rec_url and ("127.0.0.1" in rec_url or "localhost" in rec_url):
        rec_url = None

    claimed = False
    if not rec_url:
        try:
            rec_url = DooctiRecordingService.claim_unambiguous_recording(call, db)
            claimed = bool(rec_url)
        except Exception as exc:
            logger.debug(f"[CallSync] Recording lookup failed for CallLog ID={call.id}: {exc}")
            rec_url = None

    duration = 0
    if rec_url:
        try:
            duration = int(DooctiRecordingService.resolve_audio_duration(rec_url) or 0)
        except Exception as exc:
            logger.debug(f"[CallSync] Duration resolution failed for CallLog ID={call.id}: {exc}")
            duration = 0

    if duration > 0:
        status = "COMPLETED"
        answered_at = started_at
        ended_at = started_at + datetime.timedelta(seconds=duration)
        source = "recording"
    else:
        status = "MISSED" if (call.call_direction or "").upper() == "INBOUND" else "NO_ANSWER"
        answered_at = None
        ended_at = started_at
        source = "no_evidence"

    if dry_run:
        return {
            "call_log_id": call.id,
            "would_set_status": status,
            "would_set_duration": duration,
            "would_set_recording": rec_url if claimed else None,
            "source": source,
        }

    call.call_status = status
    call.duration_seconds = duration
    call.answered_at = answered_at
    call.ended_at = ended_at
    if rec_url and not call.recording_url:
        call.recording_url = rec_url

    return {
        "call_log_id": call.id,
        "provider_call_id": call.provider_call_id,
        "phone": call.to_number or call.from_number,
        "direction": call.call_direction,
        "call_status": status,
        "duration": duration,
        "recording_url": call.recording_url,
        "source": source,
    }


def finalize_stale_calls(
    db,
    stale_after_minutes: int = STALE_AFTER_MINUTES,
    max_age_hours: int = 72,
    limit: int = 200,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Closes CallLog rows that have been stuck in an active state far longer than any
    real ring/answer could last. Idempotent: rows already terminal are never touched.

    Only recent sessions are reconciled (``max_age_hours``) so deploying this fix never
    rewrites old, already-reviewed call history.
    """
    cutoff = get_ist_now() - datetime.timedelta(minutes=stale_after_minutes)
    recent_cutoff = get_ist_now() - datetime.timedelta(hours=max_age_hours)
    rows = (
        db.query(CallLog)
        .filter(
            CallLog.call_status.in_(ACTIVE_CALL_STATUSES),
            or_(
                and_(CallLog.started_at.isnot(None), CallLog.started_at <= cutoff),
                and_(CallLog.started_at.is_(None), CallLog.created_at <= cutoff),
            ),
            or_(
                and_(CallLog.started_at.isnot(None), CallLog.started_at >= recent_cutoff),
                and_(CallLog.started_at.is_(None), CallLog.created_at >= recent_cutoff),
            ),
        )
        .order_by(asc(CallLog.id))
        .limit(limit)
        .all()
    )

    closed: List[Dict[str, Any]] = []
    for call in rows:
        try:
            result = _finalize_one(db, call, dry_run=dry_run)
            if not dry_run:
                db.commit()
            closed.append(result)
            logger.info(
                f"🧹 [CallSync] Finalized stale CallLog ID={result['call_log_id']} "
                f"provider_call_id={result.get('provider_call_id')} "
                f"status={result.get('call_status') or result.get('would_set_status')} "
                f"duration={result.get('duration', result.get('would_set_duration'))}s "
                f"source={result.get('source')}"
            )
        except Exception as exc:
            db.rollback()
            logger.warning(f"[CallSync] Failed to finalize CallLog ID={getattr(call, 'id', '?')}: {exc}")

    return {
        "inspected": len(rows),
        "finalized": len(closed),
        "dry_run": dry_run,
        "calls": closed,
    }


def recover_terminal_calls_with_recordings(
    db,
    lookback_hours: int = 12,
    limit: int = 50,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Upgrades calls that were closed without audio (0s, NO_ANSWER/MISSED by the browser
    hangup path) when the provider recording proves the call was actually connected.

    This covers the case where the CDR webhook is lost but the recording exists: the
    real talk time is recovered from the audio artifact instead of showing 0 seconds.
    Only unambiguous, unused recordings are attached (see claim_unambiguous_recording).
    """
    since = get_ist_now() - datetime.timedelta(hours=lookback_hours)
    rows = (
        db.query(CallLog)
        .filter(
            CallLog.call_status.in_(["NO_ANSWER", "MISSED", "BUSY", "FAILED"]),
            CallLog.recording_url.is_(None),
            or_(CallLog.duration_seconds.is_(None), CallLog.duration_seconds <= 0),
            CallLog.created_at >= since,
        )
        .order_by(desc(CallLog.id))
        .limit(limit)
        .all()
    )

    recovered: List[Dict[str, Any]] = []
    for call in rows:
        try:
            rec_url = DooctiRecordingService.claim_unambiguous_recording(call, db)
            if not rec_url:
                continue
            duration = int(DooctiRecordingService.resolve_audio_duration(rec_url) or 0)
            if duration <= 0:
                continue
            started_at = call.started_at or call.created_at or get_ist_now()
            result = {
                "call_log_id": call.id,
                "provider_call_id": call.provider_call_id,
                "phone": call.to_number or call.from_number,
                "direction": call.call_direction,
                "previous_status": call.call_status,
                "call_status": "COMPLETED",
                "duration": duration,
                "recording_url": rec_url,
            }
            if not dry_run:
                call.call_status = "COMPLETED"
                call.duration_seconds = duration
                call.recording_url = rec_url
                call.answered_at = started_at
                call.ended_at = started_at + datetime.timedelta(seconds=duration)
                db.commit()
            recovered.append(result)
            logger.info(
                f"🎧 [CallSync] Recovered answered call from recording: CallLog ID={call.id} "
                f"duration={duration}s (was {call.call_status if not dry_run else result['previous_status']})"
            )
        except Exception as exc:
            db.rollback()
            logger.warning(f"[CallSync] Recording recovery failed for CallLog ID={getattr(call, 'id', '?')}: {exc}")

    return {
        "inspected": len(rows),
        "recovered": len(recovered),
        "dry_run": dry_run,
        "calls": recovered,
    }


UNANSWERED_CDR_STATUSES = {
    "NOANSWER",
    "NO ANSWER",
    "NO_ANSWER",
    "MISSED",
    "BUSY",
    "FAILED",
    "CANCEL",
    "CANCELLED",
    "CANCELED",
    "ABANDON",
    "ABANDONED",
}

_ZERO_ANSWER_TIMES = {
    "",
    "0000-00-00 00:00:00",
    "0000-00-00",
    "0000-00-00T00:00:00",
    "null",
    "none",
}


def _hms_to_seconds(value) -> Optional[int]:
    """Parses DooCTI's ``HH:MM:SS`` talk time (also accepts plain seconds)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    parts = text.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        nums = [int(float(p)) for p in parts]
    except (TypeError, ValueError):
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return nums[0] * 60 + nums[1]


def _parse_cdr_datetime(value) -> Optional[datetime.datetime]:
    text = str(value or "").strip()
    if text.lower() in _ZERO_ANSWER_TIMES:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _cdr_says_unanswered(row: Dict[str, Any]) -> bool:
    """
    True only when DooCTI's own CDR says the call never connected.

    Requires BOTH a non-answered status and a zero talk time. If either signal
    is missing or ambiguous the row is left alone.
    """
    status = (
        str(row.get("status") or "").strip().upper().replace("_", " ").replace("-", " ")
    )
    if status not in UNANSWERED_CDR_STATUSES:
        return False

    talk = _hms_to_seconds(row.get("talk_times"))
    if talk is None:
        talk = _hms_to_seconds(row.get("talk_time"))
    if talk is None or talk > 0:
        return False

    answer_raw = str(row.get("answer_time") or "").strip()
    if answer_raw and answer_raw.lower() not in _ZERO_ANSWER_TIMES:
        return False
    return True


def reconcile_unanswered_calls_with_cdr(
    db,
    days_back: int = 7,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Corrects call rows whose CRM duration is really ring time.

    DooCTI's CDR is authoritative: when it reports an unanswered status with
    ``talk_times = 00:00:00`` and no answer time, the call never connected, so
    the CRM must not show a 43s / 74s "conversation". Matching is always by the
    exact provider uniqueid.

    A row that already holds real audio (or a positive recording duration) is
    never downgraded: proof of audio outranks a contradictory status string.
    Nothing is deleted, and only ``call_status`` / ``duration_seconds`` /
    ``answered_at`` / ``ended_at`` are touched.
    """
    cdr = DooctiRecordingService.fetch_authoritative_call_log(db, days_back=days_back)
    if not cdr:
        return {
            "status": "skipped",
            "reason": "No DooCTI CDR data (credentials missing or provider unavailable).",
            "inspected": 0,
            "updated": 0,
            "calls": [],
        }

    since = get_ist_now() - datetime.timedelta(days=days_back)
    rows = (
        db.query(CallLog)
        .filter(
            CallLog.created_at >= since,
            CallLog.provider_call_id.isnot(None),
            CallLog.provider.ilike("%DOOCTI%"),
        )
        .order_by(desc(CallLog.id))
        .limit(2000)
        .all()
    )

    updated: List[Dict[str, Any]] = []
    stats = {
        "inspected": len(rows),
        "cdr_rows": len(cdr),
        "matched": 0,
        "already_answered": 0,
        "has_audio": 0,
        "already_correct": 0,
        "cleared_placeholders": 0,
    }
    base_url = DooctiRecordingService.get_configured_base_url(db)
    skipped: List[Dict[str, Any]] = []
    for call in rows:
        prov_id = str(call.provider_call_id or "").strip()
        cdr_row = cdr.get(prov_id)
        if not cdr_row:
            continue
        stats["matched"] += 1
        if not _cdr_says_unanswered(cdr_row):
            stats["already_answered"] += 1
            if len(skipped) < 10:
                skipped.append({
                    "provider_call_id": prov_id,
                    "reason": "provider_says_answered",
                    "provider_status": cdr_row.get("status"),
                    "provider_talk_time": cdr_row.get("talk_times"),
                })
            continue

        # Audio is proof of a connected call; never contradict it. A stored link
        # is only proof when the object actually contains audio: DooCTI writes a
        # 144-byte header-only MP3 for unanswered attempts.
        cleared_placeholder = False
        stored_url = str(call.recording_url or "").strip()
        if stored_url:
            audio_url = DooctiRecordingService.canonical_storage_url(
                stored_url, base_url
            )
            is_stub = (
                audio_url.startswith(("http://", "https://"))
                and DooctiRecordingService.is_configured_storage_url(audio_url, base_url)
                and DooctiRecordingService.is_definitely_empty_recording(audio_url)
            )
            if not is_stub:
                stats["has_audio"] += 1
                if len(skipped) < 10:
                    skipped.append({
                        "provider_call_id": prov_id,
                        "reason": "call_has_recording",
                        "recording_url": stored_url,
                    })
                continue
            # Release the dead link only (the file and the call row stay).
            cleared_placeholder = True
            stats["cleared_placeholders"] += 1
        if int(call.recording_duration_seconds or 0) > 0 and not cleared_placeholder:
            stats["has_audio"] += 1
            continue

        direction = str(call.call_direction or "").upper()
        new_status = "MISSED" if direction == "INBOUND" else "NO_ANSWER"
        new_duration = 0
        ended_at = _parse_cdr_datetime(cdr_row.get("end_time")) or call.ended_at

        already_correct = (
            str(call.call_status or "").upper() == new_status
            and int(call.duration_seconds or 0) == 0
            and call.answered_at is None
        )
        if already_correct and not cleared_placeholder:
            stats["already_correct"] += 1
            continue

        change = {
            "call_log_id": call.id,
            "provider_call_id": prov_id,
            "phone": call.to_number or call.from_number,
            "direction": direction,
            "previous_status": call.call_status,
            "previous_duration": int(call.duration_seconds or 0),
            "call_status": new_status,
            "duration": new_duration,
            "provider_status": cdr_row.get("status"),
            "provider_talk_time": cdr_row.get("talk_times"),
            "provider_billsec": cdr_row.get("billsec"),
            "cleared_placeholder_recording": cleared_placeholder,
        }
        updated.append(change)
        if dry_run:
            continue

        call.call_status = new_status
        call.duration_seconds = new_duration
        call.answered_at = None
        if ended_at:
            call.ended_at = ended_at
        if cleared_placeholder:
            call.recording_url = None
            call.recording_id = None
            call.recording_duration_seconds = None
            call.recording_source = None
            call.recording_attached_at = None
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"[CallSync] CDR reconcile commit failed for CallLog ID={call.id}: {exc}"
            )
            updated.pop()
            continue
        logger.info(
            f"📞 [CallSync] CDR reconcile: CallLog ID={call.id} "
            f"uniqueid={prov_id} {change['previous_status']}/"
            f"{change['previous_duration']}s -> {new_status}/0s "
            f"(DooCTI {cdr_row.get('status')}, talk {cdr_row.get('talk_times')})."
        )

    return {
        "status": "success",
        **stats,
        "updated": len(updated),
        "dry_run": dry_run,
        "calls": updated,
        "skipped": skipped,
    }


def _run_cdr_reconciler(days_back: int) -> Dict[str, Any]:
    """Runs one CDR reconciliation pass with its own short-lived DB session."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        return reconcile_unanswered_calls_with_cdr(db, days_back=days_back)
    finally:
        db.close()


async def start_cdr_reconcile_scheduler(
    interval_seconds: int = 1800,
    days_back: int = 7,
):
    """
    Periodically aligns recent call status/duration with DooCTI's CDR report.

    Runs on a slow cadence because it is a correction pass, not a live feed.
    The first pass happens on startup so ring-time rows are fixed immediately
    after a deploy.
    """
    import asyncio

    logger.info(
        f"CDR reconciliation scheduler started (last {days_back} day(s), "
        f"every {interval_seconds}s)."
    )
    while True:
        try:
            result = await asyncio.to_thread(_run_cdr_reconciler, days_back)
            if result.get("updated"):
                logger.info(
                    f"📞 [CallSync] CDR reconciliation corrected "
                    f"{result['updated']} call(s)."
                )
        except Exception as exc:
            logger.warning(f"[CallSync] CDR reconciliation failed: {exc}")
        await asyncio.sleep(interval_seconds)


def _run_reconciler(stale_after_minutes: int) -> Dict[str, Any]:
    """Runs one scheduler iteration with its own short-lived DB session."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        stale = finalize_stale_calls(db, stale_after_minutes=stale_after_minutes)
        recovered = recover_terminal_calls_with_recordings(db, lookback_hours=12)
        return {"stale": stale, "recovered": recovered}
    finally:
        db.close()


async def start_call_reconciler(interval_seconds: int = 60, stale_after_minutes: int = STALE_AFTER_MINUTES):
    """Periodically closes orphaned DooCTI call sessions that never received a CDR."""
    import asyncio

    logger.info(
        f"Call session reconciler started (stale after {stale_after_minutes} min, "
        f"every {interval_seconds}s)."
    )
    while True:
        try:
            await asyncio.to_thread(_run_reconciler, stale_after_minutes)
        except Exception as exc:
            logger.warning(f"[CallSync] Reconciler iteration failed: {exc}")
        await asyncio.sleep(interval_seconds)
