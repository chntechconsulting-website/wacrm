# Android Mobile SIM Call Recording – Device Compatibility Report

> **Status: implementation complete, real-device verification pending.**
> No Samsung, Vivo or Oppo hardware was attached to the build environment used
> for this change. Nothing in this report should be read as a claim that
> automatic SIM-call recording is universally available. The matrix below
> records what the implementation can detect and what must still be verified on
> physical devices.

## 1. Scope and compliance position

- Android has **no public API** that allows a third-party app to record cellular
  call audio. WACRM therefore never records calls.
- WACRM imports files that the manufacturer's own dialer/recorder has already
  produced. Import is always user-authorised:
  - Storage Access Framework (SAF) document picker (`ACTION_OPEN_DOCUMENT`), or
  - read-only MediaStore audio access granted at runtime, or
  - Android share sheet ("Share → WACRM") from the OEM recorder.
- The implementation does **not** use AccessibilityService, hidden microphone
  capture, root/privileged permissions, security bypasses, or silent recording.
- Where a manufacturer keeps its recordings in a private directory, automatic
  discovery is impossible and the app reports **Manual import only**. It does
  not guess or attach another call's audio.
- Consent is explicit and revocable. The backend also rejects `DEVICE` uploads
  without a consent flag.
- Background synchronization is **opportunistic**: the sync coordinator runs
  when the app starts or resumes, and only reads files Android exposes via
  MediaStore or files the employee selected through SAF. It does not run a
  hidden background recorder, a foreground microphone service, or bypass Android
  background-execution limits.

## 2. Capability model exposed to Flutter

`MobileCallRecordingManager` (Kotlin) reports:

| Field | Meaning |
| --- | --- |
| `manufacturer`, `brand`, `model`, `device` | Build identity |
| `androidVersion`, `androidSdk` | Runtime OS level |
| `oemFamily` | SAMSUNG, VIVO, OPPO, REALME, ONEPLUS, XIAOMI, HUAWEI, HONOR, GOOGLE, MOTOROLA, OTHER |
| `nativeDialerPackage` | Package resolved from `ACTION_DIAL` |
| `oemRecorderPackages` | Known OEM recorder packages actually installed |
| `callLogPermission` | `READ_CALL_LOG` granted |
| `audioPermission` | `READ_MEDIA_AUDIO` (Android 13+) or `READ_EXTERNAL_STORAGE` (≤ Android 12) granted |
| `safSupported` | Always true on supported Android versions |
| `mediaStoreAccessible` | Audio permission present |
| `mediaStoreRecordingCount` | Readable non-music audio rows in the last 30 days (diagnostics only) |
| `recordingFolderHints` | `RELATIVE_PATH` values seen for those rows, e.g. `Recordings/Call/` |
| `oemRecordingMayExist` | OEM is known to ship dialer recording on some models/regions |
| `oemRecordingSupport` | Honest label; no public API is claimed |
| `recordingCapability` | `AUTOMATIC_MEDIASTORE` (audio access granted) or `MANUAL_IMPORT_ONLY` |
| `automaticSyncSupported` | True when read-only audio media access is granted; an individual call may still have no matching file |
| `manualImportSupported` | Always true |
| `recentMediaStoreRecordings` | Up to 5 recently modified, non-music audio rows (diagnostics only) |
| `notes` | Human-readable limitations for the capability sheet |

## 3. Android version behaviour

| Android | Media permission | Recording import path | Automatic MediaStore discovery |
| --- | --- | --- | --- |
| 10 (API 29) | `READ_EXTERNAL_STORAGE` | SAF + share sheet | Only if files are MediaStore-visible |
| 11 (API 30) | `READ_EXTERNAL_STORAGE` | SAF + share sheet | Only if files are MediaStore-visible |
| 12 / 12L (31–32) | `READ_EXTERNAL_STORAGE` | SAF + share sheet | Only if files are MediaStore-visible |
| 13 (33) | `READ_MEDIA_AUDIO` | SAF + share sheet | Yes for audio exposed in MediaStore |
| 14 (34) | `READ_MEDIA_AUDIO` | SAF + share sheet | Yes for audio exposed in MediaStore |
| 15 (35) | `READ_MEDIA_AUDIO` | SAF + share sheet | Yes for audio exposed in MediaStore |
| 16+ | `READ_MEDIA_AUDIO` (as published) | SAF + share sheet | Depends on OEM/OS scoping; re-verify |

Notes:

- Android 13+ separates audio media access from call logs. Both permissions are
  optional; denial degrades gracefully to manual import / “Recording
  Unavailable”.
- Android scoped storage may hide OEM folders (`/Android/data`, private app
  directories, some vendor directories). SAF remains available because the
  employee chooses the file.
- Work-profile / MDM policies, carrier firmware and region can remove the OEM
  recording feature entirely.

## 4. OEM compatibility matrix (to be verified on hardware)

Legend: **TBD** = not yet verified; **Impl** = implementation path available.

| OEM | Typical OEM dialer recording | Typical folder / access | Automatic discovery expected | Manual import | Status |
| --- | --- | --- | --- | --- | --- |
| Samsung (One UI) | Available on selected models/regions; may be disabled by firmware/carrier | Internal storage, Recordings/Call; often not MediaStore-indexed | Usually no; SAF or share sheet | Impl | **TBD** |
| Vivo (Funtouch / OriginOS) | Available on many models/regions | `Record/CallRecord`, Recordings; may be visible via MediaStore | Model-dependent | Impl | **TBD** |
| Oppo (ColorOS) | Available on many models/regions | `Recordings/Call`, `Music/Recordings`; may be visible via MediaStore | Model-dependent | Impl | **TBD** |
| Realme (realme UI) | Same family as ColorOS | Same as ColorOS | Model-dependent | Impl | **TBD** |
| OnePlus (OxygenOS) | Selected models/regions | `Recordings/Call` | Model-dependent | Impl | **TBD** |
| Xiaomi / Redmi / POCO (MIUI/HyperOS) | Available on many models/regions | `MIUI/sound_recorder/call_rec`; often not MediaStore-visible | Usually no | Impl | **TBD** |
| Huawei / Honor | Available on some models/regions | `Recordings`, `Sounds` | Model-dependent | Impl | **TBD** |
| Google Pixel | No native call recording in most regions | Not applicable | No | Impl (external file) | **TBD** |
| Other Android | Depends on OEM/carrier | Unknown | No assumption | Impl | **TBD** |

> Do not mark an OEM as “automatic sync supported” until the capability sheet on
> that exact device reports `AUTOMATIC_MEDIASTORE` and a real recording was
> uploaded and played back.

## 5. Per-device verification template

Record one row per tested device:

| Field | Value |
| --- | --- |
| Manufacturer / model | |
| Android version / API level | |
| Build fingerprint | |
| Native dialer package | |
| OEM recording feature present and enabled? | |
| Recording folder / accessibility | |
| Capability reported by WACRM | `AUTOMATIC_MEDIASTORE` / `MANUAL_IMPORT_ONLY` |
| Recording file accessible via SAF? | |
| Recording file discoverable via MediaStore? | |
| Automatic sync succeeded? | |
| Manual import succeeded? | |
| Playback verified in mobile app? | |
| Playback verified in web CRM? | |
| Notes / region / carrier | |

## 6. On-device diagnostics (Samsung first)

Open the shield icon in the Calls app bar → **Copy diagnostics**. It returns the
device/OS identity, OEM family, dialer package, audio-permission state, readable
recording count, recording folder hints and any OEM warnings. Use it to fill the
per-device template and to report a failed import.

If `Readable recordings` is 0 while the Samsung dialer has produced files, the
recording folder is not indexed by Android media scan. Use **Choose a recording
file** (SAF) or share the file from Samsung's recorder app. This is a device
limitation, not an upload failure.

Backing out of the system file picker is treated as a cancellation and does not
show a “no recording found” error.

**Deployment requirement:** recordings are served from
`/api/ivr/media/recordings/{call_id}/{filename}`. Reverse proxies must forward
`/api/*` to FastAPI (the generic `/uploads/*` mount is not publicly routed in
production). The mobile app rewrites legacy `/uploads/recordings/...` links to
this route automatically.

## 7. Expected limitations

- **No universal automatic SIM recording.** The app can only see files Android
  exposes; some OEMs keep recordings private.
- **No recording when the OEM feature is off.** WACRM does not enable or bypass
  the dialer's recording setting.
- **No audio when the file is protected/encrypted** by the OEM or MDM.
- **DooCTI/PBX calls remain unchanged**; their recordings come from the PBX and
  are not handled by this module.
- **Consent is mandatory** for `DEVICE` uploads; the backend rejects them
  otherwise.
