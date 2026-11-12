package com.wacrm.mobile

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.provider.OpenableColumns
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.UUID

/**
 * Dedicated Android module for Mobile SIM call recordings.
 *
 * Design and compliance boundaries:
 * - WACRM never records cellular audio. It only imports files that the OEM
 *   dialer/recorder has already produced, and only after the employee grants
 *   access through the Storage Access Framework (SAF) or an explicit runtime
 *   media permission.
 * - No AccessibilityService, hidden microphone capture, privileged permission
 *   escalation, root/Jailbreak bypass or silent background recording is used.
 * - Automatic discovery is limited to MediaStore audio that Android exposes to
 *   ordinary apps. When a manufacturer does not expose its recordings, the
 *   module reports MANUAL_IMPORT_ONLY instead of pretending to support it.
 *
 * Channel: wacrm/mobile_call_recording
 */
class MobileCallRecordingManager(
    private val context: Context,
    private val activity: Activity?,
    messenger: BinaryMessenger,
) : MethodChannel.MethodCallHandler {
    companion object {
        private const val CHANNEL = "wacrm/mobile_call_recording"
        private const val PICK_REQUEST_CODE = 0x5243
        private const val PREFS = "wacrm_call_recording"
        private const val KEY_UPLOAD_STATUS_PREFIX = "upload_status_"
        private const val MAX_RECORDING_BYTES = 25L * 1024 * 1024
        private const val MIN_RECORDING_BYTES = 1024L
        private const val RECENT_WINDOW_DAYS = 30
        private val RECORDING_EXTENSIONS = setOf(
            "mp3", "m4a", "aac", "wav", "ogg", "opus", "amr", "3gp", "3gpp",
            "caf", "webm", "mp4",
        )
        private val OEM_RECORDER_PACKAGES = mapOf(
            "SAMSUNG" to listOf(
                "com.sec.android.app.voicenote",
                "com.samsung.android.app.voicenote",
            ),
            "VIVO" to listOf("com.vivo.recorder", "com.vivo.soundrecorder"),
            "OPPO" to listOf("com.coloros.recorder", "com.oplus.recorder"),
            "REALME" to listOf("com.coloros.recorder", "com.realme.recorder"),
            "ONEPLUS" to listOf("com.oplus.recorder", "com.oneplus.soundrecorder"),
            "XIAOMI" to listOf("com.miui.recorder", "com.android.soundrecorder"),
            "HUAWEI" to listOf("com.huawei.soundrecorder"),
            "HONOR" to listOf("com.hihonor.soundrecorder"),
            "GOOGLE" to listOf("com.google.android.soundrecorder"),
        )
    }

    private val channel = MethodChannel(messenger, CHANNEL)
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private var pendingPickResult: MethodChannel.Result? = null

    init {
        channel.setMethodCallHandler(this)
    }

    fun dispose() {
        channel.setMethodCallHandler(null)
        pendingPickResult = null
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getCapability" -> result.success(buildCapability())
            "pickRecordingFile" -> pickRecordingFile(result)
            "findRecordingForCall" -> findRecordingForCall(call, result)
            "setUploadStatus" -> setUploadStatus(call, result)
            "getUploadStatus" -> result.success(getUploadStatus(call))
            "clearUploadStatus" -> result.success(clearUploadStatus(call))
            else -> result.notImplemented()
        }
    }

    // ------------------------------------------------------------------
    // Runtime capability detection
    // ------------------------------------------------------------------

    private fun oemFamily(): String {
        val marker = "${Build.MANUFACTURER} ${Build.BRAND}".uppercase()
        return when {
            marker.contains("SAMSUNG") -> "SAMSUNG"
            marker.contains("VIVO") -> "VIVO"
            marker.contains("OPPO") -> "OPPO"
            marker.contains("REALME") -> "REALME"
            marker.contains("ONEPLUS") || marker.contains("ONE PLUS") -> "ONEPLUS"
            marker.contains("XIAOMI") || marker.contains("REDMI") ||
                marker.contains("POCO") -> "XIAOMI"
            marker.contains("HONOR") -> "HONOR"
            marker.contains("HUAWEI") -> "HUAWEI"
            marker.contains("GOOGLE") -> "GOOGLE"
            marker.contains("MOTOROLA") -> "MOTOROLA"
            else -> "OTHER"
        }
    }

    private fun hasCallLogPermission(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        return context.checkSelfPermission(Manifest.permission.READ_CALL_LOG) ==
            PackageManager.PERMISSION_GRANTED
    }

    private fun hasAudioPermission(): Boolean {
        return when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU ->
                context.checkSelfPermission(Manifest.permission.READ_MEDIA_AUDIO) ==
                    PackageManager.PERMISSION_GRANTED
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ->
                context.checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) ==
                    PackageManager.PERMISSION_GRANTED
            else -> true
        }
    }

    private fun nativeDialerPackage(): String? {
        return try {
            val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:"))
            context.packageManager.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY)
                ?.activityInfo?.packageName
        } catch (_: Exception) {
            null
        }
    }

    private fun installedRecorderPackages(): List<String> {
        val known = OEM_RECORDER_PACKAGES[oemFamily()] ?: emptyList()
        return known.filter { pkg ->
            try {
                context.packageManager.getPackageInfo(pkg, 0)
                true
            } catch (_: PackageManager.NameNotFoundException) {
                false
            }
        }
    }

    /**
     * MediaStore audio row, read across every readable external volume.
     * Only metadata is read; file contents are opened later, after a unique
     * match and after the employee has consented.
     */
    private data class AudioRow(
        val uri: Uri,
        val name: String,
        val durationMs: Long,
        val modifiedMs: Long,
        val size: Long,
        val mimeType: String,
        val relativePath: String,
    )

    private fun audioVolumes(): List<String> {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return listOf(MediaStore.VOLUME_EXTERNAL)
        }
        return try {
            MediaStore.getExternalVolumeNames(context).toList().ifEmpty {
                listOf(MediaStore.VOLUME_EXTERNAL)
            }
        } catch (_: Exception) {
            listOf(MediaStore.VOLUME_EXTERNAL)
        }
    }

    private fun volumeUri(volume: String): Uri {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.Audio.Media.getContentUri(volume)
        } else {
            MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
        }
    }

    private fun queryAudioRows(
        sinceSec: Long,
        untilSec: Long,
        limit: Int = 200,
    ): List<AudioRow> {
        if (!hasAudioPermission()) return emptyList()
        val projection = buildList {
            add(MediaStore.Audio.Media._ID)
            add(MediaStore.Audio.Media.DISPLAY_NAME)
            add(MediaStore.Audio.Media.DURATION)
            add(MediaStore.Audio.Media.DATE_MODIFIED)
            add(MediaStore.Audio.Media.SIZE)
            add(MediaStore.Audio.Media.MIME_TYPE)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                add(MediaStore.Audio.Media.RELATIVE_PATH)
            }
        }.toTypedArray()
        val selection = buildString {
            append(MediaStore.Audio.Media.IS_MUSIC).append(" = 0")
            append(" AND ").append(MediaStore.Audio.Media.DURATION).append(" > 0")
            append(" AND ").append(MediaStore.Audio.Media.DATE_MODIFIED)
            append(" >= ? AND ").append(MediaStore.Audio.Media.DATE_MODIFIED).append(" <= ?")
        }
        val rows = mutableListOf<AudioRow>()
        val seen = mutableSetOf<String>()
        for (volume in audioVolumes()) {
            try {
                context.contentResolver.query(
                    volumeUri(volume),
                    projection,
                    selection,
                    arrayOf(sinceSec.toString(), untilSec.toString()),
                    "${MediaStore.Audio.Media.DATE_MODIFIED} DESC",
                )?.use { cursor ->
                    val idIndex = cursor.getColumnIndex(MediaStore.Audio.Media._ID)
                    val nameIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DISPLAY_NAME)
                    val durationIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DURATION)
                    val modifiedIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DATE_MODIFIED)
                    val sizeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.SIZE)
                    val mimeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.MIME_TYPE)
                    val pathIndex = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        cursor.getColumnIndex(MediaStore.Audio.Media.RELATIVE_PATH)
                    } else {
                        -1
                    }
                    while (cursor.moveToNext() && rows.size < limit) {
                        val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                        if (id <= 0L) continue
                        val uri = Uri.withAppendedPath(volumeUri(volume), id.toString())
                        if (!seen.add(uri.toString())) continue
                        rows.add(
                            AudioRow(
                                uri = uri,
                                name = (if (nameIndex >= 0) {
                                    cursor.getString(nameIndex)
                                } else {
                                    null
                                }).orEmpty(),
                                durationMs = if (durationIndex >= 0) {
                                    cursor.getLong(durationIndex)
                                } else {
                                    0L
                                },
                                modifiedMs =
                                    (if (modifiedIndex >= 0) {
                                        cursor.getLong(modifiedIndex)
                                    } else {
                                        0L
                                    }) * 1000L,
                                size = if (sizeIndex >= 0) cursor.getLong(sizeIndex) else 0L,
                                mimeType = (if (mimeIndex >= 0) {
                                    cursor.getString(mimeIndex)
                                } else {
                                    null
                                }).orEmpty(),
                                relativePath = if (pathIndex >= 0) {
                                    cursor.getString(pathIndex).orEmpty()
                                } else {
                                    ""
                                },
                            ),
                        )
                    }
                }
            } catch (_: Exception) {
                // A volume can be unmounted, ejected or policy-protected; keep
                // querying the remaining volumes rather than failing entirely.
            }
        }
        return rows.sortedByDescending { it.modifiedMs }
    }

    private fun buildCapability(): Map<String, Any?> {
        val family = oemFamily()
        val audioPermission = hasAudioPermission()
        val nowSec = System.currentTimeMillis() / 1000L
        val sinceSec = nowSec - RECENT_WINDOW_DAYS * 24L * 60L * 60L
        val readableRows = if (audioPermission) {
            queryAudioRows(sinceSec, nowSec + 60L, limit = 200)
        } else {
            emptyList()
        }
        val recents = readableRows.take(5).map { row ->
            mapOf(
                "id" to row.uri.lastPathSegment,
                "name" to row.name,
                "durationMs" to row.durationMs,
                "modifiedMs" to row.modifiedMs,
                "size" to row.size,
                "mimeType" to row.mimeType,
                "relativePath" to row.relativePath,
            )
        }
        val folderHints = readableRows
            .map { it.relativePath.trim() }
            .filter { it.isNotEmpty() }
            .distinct()
            .take(8)
        // "Automatic discovery" is an ability, not a promise: it means the app
        // is allowed to query MediaStore. Whether a matching recording exists is
        // decided per call by the strict matcher.
        val automaticSync = audioPermission
        val recorderPackages = installedRecorderPackages()
        val oemRecordingMayExist = family in setOf(
            "SAMSUNG", "VIVO", "OPPO", "REALME", "ONEPLUS", "XIAOMI", "HUAWEI",
            "HONOR", "MOTOROLA", "OTHER",
        )
        val capability = if (automaticSync) "AUTOMATIC_MEDIASTORE" else "MANUAL_IMPORT_ONLY"
        val notes = buildList {
            add(
                "Android has no public API that lets a third-party app record " +
                    "cellular call audio. WACRM only imports files created by the " +
                    "device's own dialer/recorder after the employee grants access."
            )
            if (!audioPermission) {
                add(
                    "Audio media permission is not granted, so automatic file " +
                        "discovery is disabled. Manual import through the system " +
                        "file picker still works."
                )
            }
            if (audioPermission && readableRows.isEmpty()) {
                add(
                    "No recent readable MediaStore recordings were found. If the " +
                        "OEM dialer records calls, its folder may not be indexed by " +
                        "Android media scan; use Choose a file or share from the " +
                        "OEM recorder instead."
                )
            }
            if (family == "SAMSUNG") {
                add(
                    "Samsung One UI typically stores call recordings in " +
                        "Recordings/Call. If they do not appear in the search, use " +
                        "Choose a file (Storage Access Framework) or Samsung's " +
                        "recorder share action."
                )
            }
            if (recorderPackages.isEmpty()) {
                add("No known OEM recorder app was detected on this device.")
            }
            add(
                "Manufacturer call-recording availability can depend on region, " +
                    "model, carrier firmware and whether the user enabled it in " +
                    "the native dialer. This app never enables or bypasses it."
            )
        }
        return mapOf(
            "manufacturer" to Build.MANUFACTURER,
            "brand" to Build.BRAND,
            "model" to Build.MODEL,
            "device" to Build.DEVICE,
            "androidVersion" to Build.VERSION.RELEASE,
            "androidSdk" to Build.VERSION.SDK_INT,
            "oemFamily" to family,
            "nativeDialerPackage" to nativeDialerPackage(),
            "oemRecorderPackages" to recorderPackages,
            "callLogPermission" to hasCallLogPermission(),
            "audioPermission" to audioPermission,
            "safSupported" to true,
            "mediaStoreAccessible" to audioPermission,
            "oemRecordingMayExist" to oemRecordingMayExist,
            "oemRecordingSupport" to if (oemRecordingMayExist) {
                "OEM_DIALER_RECORDING_MAY_EXIST_NO_PUBLIC_API"
            } else {
                "NO_KNOWN_OEM_RECORDING"
            },
            "recordingCapability" to capability,
            "automaticSyncSupported" to automaticSync,
            "manualImportSupported" to true,
            "mediaStoreRecordingCount" to readableRows.size,
            "recordingFolderHints" to folderHints,
            "recentMediaStoreRecordings" to recents,
            "notes" to notes,
        )
    }

    // ------------------------------------------------------------------
    // User-authorized import through the Storage Access Framework
    // ------------------------------------------------------------------

    private fun pickRecordingFile(result: MethodChannel.Result) {
        if (pendingPickResult != null) {
            result.error("PICK_IN_PROGRESS", "A recording picker is already open.", null)
            return
        }
        // The picker needs the foreground activity. The headless WorkManager
        // engine registers this module without one, so it must fail closed
        // instead of attempting to start an activity from the background.
        val host = activity
        if (host == null) {
            result.error(
                "PICKER_UNAVAILABLE",
                "A recording can only be chosen while the app is open.",
                null,
            )
            return
        }
        pendingPickResult = result
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            // Some OEM recorders save .3gp/.m4a under video or generic types;
            // listing audio plus the common call-recording containers keeps the
            // file visible without requesting broad storage access.
            type = "*/*"
            putExtra(
                Intent.EXTRA_MIME_TYPES,
                arrayOf("audio/*", "video/3gpp", "application/ogg"),
            )
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        try {
            host.startActivityForResult(
                Intent.createChooser(intent, "Select call recording"),
                PICK_REQUEST_CODE,
            )
        } catch (error: Exception) {
            pendingPickResult = null
            result.error("PICKER_UNAVAILABLE", error.message, null)
        }
    }

    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        if (requestCode != PICK_REQUEST_CODE) return false
        val pending = pendingPickResult ?: return true
        pendingPickResult = null
        val uri = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null) {
            // Distinct from "no match": the employee simply backed out of the
            // system picker and nothing should be reported as a failure.
            pending.success(mapOf("cancelled" to true))
            return true
        }
        try {
            activity?.contentResolver?.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        } catch (_: Exception) {
            // Not all providers grant persistable access; the copied file
            // created below is still sufficient for this upload.
        }
        try {
            pending.success(copyRecordingToStorage(uri, "SAF_IMPORT"))
        } catch (error: RecordingVerificationException) {
            pending.error("VERIFICATION_FAILED", error.message, null)
        } catch (error: Exception) {
            pending.error("IMPORT_FAILED", error.message, null)
        }
        return true
    }

    /**
     * Strict read-only MediaStore lookup for the exact call. Returns null when
     * zero or more than one file matches; ambiguity is never resolved by
     * guessing because attaching another call's audio is worse than no file.
     */
    private fun findRecordingForCall(call: MethodCall, result: MethodChannel.Result) {
        val phone = call.argument<String>("phone").orEmpty()
        val startedAt = call.argument<Number>("startedAtMillis")?.toLong() ?: 0L
        val endedAt = call.argument<Number>("endedAtMillis")?.toLong() ?: 0L
        val durationSeconds = call.argument<Number>("durationSeconds")?.toInt() ?: 0
        if (phone.isBlank() || startedAt <= 0L || durationSeconds <= 0) {
            result.success(null)
            return
        }
        if (!hasAudioPermission()) {
            result.success(null)
            return
        }

        val callDurationMs = durationSeconds * 1000L
        val callEnd = if (endedAt > 0L) endedAt else startedAt + callDurationMs
        val phoneKey = phone.replace(Regex("[^0-9]"), "").takeLast(10)
        val toleranceMs = maxOf(8_000L, (callDurationMs * 0.20).toLong())
        // Some dialers finalise/scan the file shortly after the call ends.
        val minModifiedSec = (startedAt - 180_000L) / 1000L
        val maxModifiedSec = (callEnd + 900_000L) / 1000L

        // Read-only metadata lookup across every accessible volume. The file
        // itself is opened only after the match is proven unique.
        val candidates = queryAudioRows(minModifiedSec, maxModifiedSec, limit = 200)
            .filter { row ->
                val durationDelta = kotlin.math.abs(row.durationMs - callDurationMs)
                val nameDigits = row.name.replace(Regex("[^0-9]"), "")
                val nameMatches = phoneKey.isNotBlank() && nameDigits.contains(phoneKey)
                val durationMatches = durationDelta <= toleranceMs
                val exactDuration = durationDelta <= 5_000L
                val timeClose = kotlin.math.abs(row.modifiedMs - callEnd) <= 600_000L
                row.size in MIN_RECORDING_BYTES..MAX_RECORDING_BYTES &&
                    row.durationMs > 0L &&
                    durationMatches &&
                    (nameMatches || (exactDuration && timeClose))
            }

        if (candidates.size != 1) {
            result.success(null)
            return
        }
        val chosen = candidates.first()
        if (chosen.mimeType.isNotBlank() &&
            !chosen.mimeType.startsWith("audio/") &&
            !chosen.mimeType.startsWith("video/3gpp")
        ) {
            result.success(null)
            return
        }
        try {
            val copied = copyRecordingToStorage(chosen.uri, "MEDIASTORE_MATCH")
            result.success(
                copied + mapOf(
                    "matchedBy" to if (
                        chosen.name.replace(Regex("[^0-9]"), "").contains(phoneKey)
                    ) {
                        "filename_and_duration"
                    } else {
                        "duration_and_time"
                    },
                ),
            )
        } catch (error: RecordingVerificationException) {
            result.error("VERIFICATION_FAILED", error.message, null)
        } catch (_: Exception) {
            result.success(null)
        }
    }

    // ------------------------------------------------------------------
    // Verified copy + metadata extraction
    // ------------------------------------------------------------------

    class RecordingVerificationException(message: String) : Exception(message)

    private fun copyRecordingToStorage(uri: Uri, importSource: String): Map<String, Any?> {
        val resolver = context.contentResolver
        var displayName = "call-recording"
        var reportedSize = -1L
        try {
            resolver.query(
                uri,
                arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE),
                null,
                null,
                null,
            )?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (nameIndex >= 0) {
                        displayName = cursor.getString(nameIndex) ?: displayName
                    }
                    if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                        reportedSize = cursor.getLong(sizeIndex)
                    }
                }
            }
        } catch (_: Exception) {
            // Fall back to a generic name; the copy below still validates bytes.
        }

        val extension = displayName.substringAfterLast('.', "").lowercase()
        if (extension !in RECORDING_EXTENSIONS) {
            throw RecordingVerificationException(
                "The selected file type is not a supported call recording format.",
            )
        }
        if (reportedSize > MAX_RECORDING_BYTES) {
            throw RecordingVerificationException(
                "The recording is larger than the 25 MB limit.",
            )
        }

        // Persist the verified copy in app storage, not the cache: the durable
        // recording queue may retry the upload after a process death or an
        // offline period. Only this app-owned copy is deleted after the backend
        // confirms the upload; the OEM/MediaStore original is never touched.
        val targetDir = File(context.filesDir, "call_recordings").apply { mkdirs() }
        val target = File(targetDir, "${UUID.randomUUID()}.$extension")
        val digest = MessageDigest.getInstance("SHA-256")
        var total = 0L
        try {
            resolver.openInputStream(uri)?.use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(1024 * 1024)
                    while (true) {
                        val read = input.read(buffer)
                        if (read <= 0) break
                        total += read
                        if (total > MAX_RECORDING_BYTES) {
                            throw RecordingVerificationException(
                                "The recording is larger than the 25 MB limit.",
                            )
                        }
                        digest.update(buffer, 0, read)
                        output.write(buffer, 0, read)
                    }
                }
            } ?: throw RecordingVerificationException("Could not open the selected file.")
            if (total < MIN_RECORDING_BYTES) {
                throw RecordingVerificationException(
                    "The selected file is empty or too small to be a call recording.",
                )
            }

            val metadata = readMetadata(uri)
            val durationMs = (metadata["durationMs"] as? Long) ?: 0L
            if (durationMs <= 0L) {
                throw RecordingVerificationException(
                    "The selected file has no readable audio duration and was not imported.",
                )
            }
            val mime = (metadata["mimeType"] as? String).orEmpty().ifBlank {
                resolver.getType(uri).orEmpty().ifBlank { "audio/*" }
            }
            if (!mime.startsWith("audio/") && !mime.startsWith("video/3gpp")) {
                throw RecordingVerificationException(
                    "The selected file is not recognised as audio.",
                )
            }

            return mapOf(
                "path" to target.absolutePath,
                "name" to displayName,
                "size" to total,
                "mimeType" to mime,
                "durationMs" to durationMs,
                "checksum" to digest.digest().joinToString("") { "%02x".format(it) },
                "source" to importSource,
                "verified" to true,
                "originUri" to uri.toString(),
            )
        } catch (error: RecordingVerificationException) {
            target.delete()
            throw error
        } catch (error: Exception) {
            target.delete()
            throw RecordingVerificationException(
                "The recording could not be verified: ${error.message ?: "unknown error"}",
            )
        }
    }

    private fun readMetadata(uri: Uri): Map<String, Any?> {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, uri)
            val duration = retriever
                .extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                ?.toLongOrNull() ?: 0L
            val mime = retriever
                .extractMetadata(MediaMetadataRetriever.METADATA_KEY_MIMETYPE)
                .orEmpty()
            mapOf("durationMs" to duration, "mimeType" to mime)
        } catch (_: Exception) {
            mapOf("durationMs" to 0L, "mimeType" to "")
        } finally {
            try {
                retriever.release()
            } catch (_: Exception) {
            }
        }
    }

    // ------------------------------------------------------------------
    // Last upload status (mirrors the backend status for diagnostics)
    // ------------------------------------------------------------------

    private fun statusKey(call: MethodCall): String? {
        val callId = call.argument<String>("callId")
            ?: call.argument<Number>("callId")?.toString()
        return callId?.trim()?.takeIf { it.isNotEmpty() }
            ?.let { "$KEY_UPLOAD_STATUS_PREFIX$it" }
    }

    private fun setUploadStatus(call: MethodCall, result: MethodChannel.Result) {
        val key = statusKey(call)
        val status = call.argument<String>("status").orEmpty().uppercase()
        if (key == null || status.isBlank()) {
            result.success(false)
            return
        }
        val payload = JSONObject().apply {
            put("status", status)
            put("detail", call.argument<String>("detail").orEmpty())
            put("updatedAt", System.currentTimeMillis())
        }
        prefs.edit().putString(key, payload.toString()).apply()
        result.success(true)
    }

    private fun getUploadStatus(call: MethodCall): Map<String, Any?>? {
        val key = statusKey(call) ?: return null
        val raw = prefs.getString(key, null) ?: return null
        return try {
            val json = JSONObject(raw)
            mapOf(
                "status" to json.optString("status"),
                "detail" to json.optString("detail"),
                "updatedAt" to json.optLong("updatedAt"),
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun clearUploadStatus(call: MethodCall): Boolean {
        val key = statusKey(call) ?: return false
        prefs.edit().remove(key).apply()
        return true
    }
}
