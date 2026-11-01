# Android Mobile SIM Call Recording – Testing Report

> **Environment note:** this report covers automated tests and build
> verification performed in the development workspace. **No Samsung, Vivo,
> Oppo or other physical Android device was connected**, so the on-device test
> cases below are marked **NOT RUN** rather than claimed as passed.

## 1. Build and automated verification

| Check | Command | Result |
| --- | --- | --- |
| Backend unit/integration suite | `backend\venv\Scripts\python.exe -m unittest discover -s backend/tests -q` | **143 tests – OK** |
| Mobile recording module tests | `flutter test test/mobile_call_recording_manager_test.dart test/mobile_sim_call_service_test.dart test/call_log_model_test.dart` | **18 tests – passed** |
| Flutter static analysis | `flutter analyze` | No errors/warnings; existing info-level lint only |
| Kotlin compilation | `gradlew :app:compileDebugKotlin` | **BUILD SUCCESSFUL** |
| Web production build | `npm run build` | **Built successfully** (existing chunk-size warning only) |
| Database migration | `python backend/migrations/apply_call_recording_management_migration.py` | Applied to local MySQL `wa_crm` |

## 2. What the automated tests prove

### Backend (`backend/tests/test_mobile_recording.py`, `test_mobile_call_attempt.py`)

- Upload stores the file and marks the call `AVAILABLE`.
- Non-audio files are rejected.
- Duplicate byte-identical uploads are idempotent (same URL, no extra file).
- `DEVICE` uploads require explicit consent.
- `DEVICE` uploads require the actual duration.
- A duration mismatch is rejected and recorded as `VERIFICATION_FAILED`.
- Status endpoint accepts `PENDING_SYNC`, `RECORDING_UNAVAILABLE`,
  `UPLOAD_FAILED`, `VERIFICATION_FAILED`; `AVAILABLE` cannot be forced.
- A verified recording cannot be downgraded by a stale failure report.
- Non-device (DooCTI) calls cannot use the device recording endpoint.
- Native history rows remain idempotent and adopt the matching in-app attempt.
- Inbound mobile calls store the customer as `from_number`.

### Flutter (`mobile/test/mobile_call_recording_manager_test.dart`)

- Canonical/legacy status mapping (`RECORDING_AVAILABLE` → `AVAILABLE`,
  `RECORDING_PROCESSING` → `PENDING_SYNC`, etc.).
- A real recording URL always wins over a stale failure status.
- Capability payload parsing, OEM diagnostics and automatic-vs-manual flags.
- Consent is stored per employee, independent between employees, and revocable.
- Playback resolves the stored media URL (never the POST upload endpoint) and
  rebases managed `/uploads/...` links onto the configured backend, while
  leaving external PBX storage URLs untouched.

## 2a. On-device issues found and fixed (Samsung)

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Unable to play this recording (1/-1015)` on a call marked **Available** | The mobile player opened `POST /api/ivr/calls/{id}/recording` (the upload endpoint) instead of the stored `recording_url`. | Play now uses the call's `recording_url`; absolute, rebased or external URLs are resolved before MediaPlayer opens them. |
| `Unable to play this recording (1/-1015); HTTP 206, text/html` | Production Caddy serves the web app for `/uploads/...` (SPA fallback); it only proxies `/api/*` to FastAPI, so uploaded recordings were unreachable at their stored URL. | Added a read-only `GET /api/ivr/media/recordings/{call_id}/{filename}` route that serves the file with an explicit audio content type and HTTP Range support. Stored links are rewritten to it, including legacy rows and old app responses. |
| Picker cancellation showed “No unambiguous device recording was found” | Native picker returned `null` for both cancel and no-match. | Cancellation is a distinct result; backing out is silent. |
| Samsung recordings were not found by automatic search | Discovery was gated on already-readable recordings and only queried one volume. | Discovery uses read-only audio access and queries every external volume; capability sheet reports readable count and folder hints. |

Playback failures now include the HTTP status and content type from a
best-effort probe, making server-side 403/404/405 failures diagnosable without
ADB.

## 3. Physical-device test plan (NOT RUN – hardware unavailable)

For every device, complete the per-device template in
`docs/ANDROID_CALL_RECORDING_DEVICE_COMPATIBILITY.md` and execute:

| # | Test | Expected result | Status |
| --- | --- | --- | --- |
| 1 | Cold start with `READ_CALL_LOG` denied | Call log still logs calls; capability sheet shows no automatic discovery | **NOT RUN** |
| 2 | Grant call-log permission, sync history | Incoming/outgoing/missed rows appear once with correct duration and source `MOBILE` | **NOT RUN** |
| 3 | OEM dialer records an outgoing call, file visible in MediaStore | Status becomes `PENDING_SYNC`, then `AVAILABLE` after sync | **NOT RUN** |
| 4 | Incoming answered call with OEM recording | Exact call matched; playback works | **NOT RUN** |
| 5 | Missed/rejected call | Status `RECORDING_UNAVAILABLE`; no wrong audio attached | **NOT RUN** |
| 6 | Two calls to the same number in quick succession | Matcher refuses ambiguous files; nothing mis-associated | **NOT RUN** |
| 7 | Import a file through SAF | Metadata/duration verified; upload succeeds; backend status `AVAILABLE` | **NOT RUN** |
| 8 | Import a non-audio or wrong file | `VERIFICATION_FAILED`; call stays unattached | **NOT RUN** |
| 9 | Upload with network disabled | `UPLOAD_FAILED`; retry succeeds without duplicate | **NOT RUN** |
| 10 | Revoke consent, retry auto sync | No device file uploaded; status waits for consent | **NOT RUN** |
| 11 | Web CRM playback of a mobile recording | Same audio plays; source badge `MOBILE`; status `Available` | **NOT RUN** |
| 12 | DooCTI WebRTC call | Source `DOOCTI`, PBX recording flow unchanged | **NOT RUN** |
| 13 | Keypad and SIM calling regression | Outgoing/incoming/duration/lead mapping unchanged | **NOT RUN** |
| 14 | App restart with pending sync | No duplicates; one row per native call | **NOT RUN** |
| 15 | Android 10, 12, 13, 14, 15, 16 device coverage | Capability/status behave as documented | **NOT RUN** |

## 4. Required devices / OS coverage

Minimum real-device matrix before claiming support:

- Samsung: one One UI device on Android 10–12 and one on Android 13+.
- Vivo: one Funtouch/OriginOS device on Android 11–13 and one on Android 14+.
- Oppo: one ColorOS device on Android 11–13 and one on Android 14+.
- At least one “other” OEM (Xiaomi/Realme/OnePlus/Pixel) as a control.
- Android 16+ when a supported device/emulator is available.

Emulators are useful for permission/SAF flows but **cannot** prove OEM
recording-file availability.

## 5. Regression checklist (unchanged areas)

- [ ] Mobile SIM outgoing call metadata (lead, phone, direction, timestamps)
- [ ] Mobile SIM incoming and missed call rows
- [ ] Call duration accuracy
- [ ] Lead mapping and auto-match
- [ ] DooCTI WebRTC calling and PBX recordings
- [ ] Existing keypad / dialer flow
- [ ] Existing backend call-log filters and admin/employee views
- [ ] No duplicate call rows after repeated syncs

## 6. Sign-off

| Item | State |
| --- | --- |
| Kotlin module implemented | Yes (`MobileCallRecordingManager.kt`) |
| Flutter MethodChannel module implemented | Yes (`mobile_call_recording_manager.dart`) |
| SAF manual import | Yes |
| Capability/OEM detection | Yes |
| Consent/disclosure | Yes, enforced in app and backend |
| Recording status machine | Yes |
| Background sync scope | Opportunistic on app start/resume using only MediaStore/SAF; no hidden recorder or background-execution bypass |
| Duplicate/incorrect-association guards | Yes (native strict match + backend checksum/duration/idempotency) |
| Real-device verification | **Pending – no hardware attached** |

Do not change the final row to “complete” without attaching the filled
per-device compatibility tables and test evidence.
