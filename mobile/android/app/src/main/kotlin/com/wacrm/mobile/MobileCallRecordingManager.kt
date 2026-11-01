package com.wacrm.mobile

import android.Manifest
import android.app.Activity
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
    private val activity: Activity,
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
    private val prefs = activity.getSharedPreferences(PREFS, Activity.MODE_PRIVATE)
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
        return activity.checkSelfPermission(Manifest.permission.READ_CALL_LOG) ==
            PackageManager.PERMISSION_GRANTED
    }

    private fun hasAudioPermission(): Boolean {
        return when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU ->
                activity.checkSelfPermission(Manifest.permission.READ_MEDIA_AUDIO) ==
                    PackageManager.PERMISSION_GRANTED
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ->
                activity.checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) ==
                    PackageManager.PERMISSION_GRANTED
            else -> true
        }
    }

    private fun nativeDialerPackage(): String? {
        return try {
            val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:"))
            activity.packageManager.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY)
                ?.activityInfo?.packageName
        } catch (_: Exception) {
            null
        }
    }

    private fun installedRecorderPackages(): List<String> {
        val known = OEM_RECORDER_PACKAGES[oemFamily()] ?: emptyList()
        return known.filter { pkg ->
            try {
                activity.packageManager.getPackageInfo(pkg, 0)
                true
            } catch (_: PackageManager.NameNotFoundException) {
                false
            }
        }
    }

    private fun recentRecordings(limit: Int = 5): List<Map<String, Any?>> {
        if (!hasAudioPermission()) return emptyList()
        val sinceSec =
            (System.currentTimeMillis() - RECENT_WINDOW_DAYS * 24L * 60L * 60L * 1000L) / 1000L
        val rows = mutableListOf<Map<String, Any?>>()
        val projection = arrayOf(
            MediaStore.Audio.Media._ID,
            MediaStore.Audio.Media.DISPLAY_NAME,
            MediaStore.Audio.Media.DURATION,
            MediaStore.Audio.Media.DATE_MODIFIED,
            MediaStore.Audio.Media.SIZE,
            MediaStore.Audio.Media.MIME_TYPE,
        )
        val selection = buildString {
            append(MediaStore.Audio.Media.IS_MUSIC).append(" = 0")
            append(" AND ").append(MediaStore.Audio.Media.DATE_MODIFIED).append(" >= ?")
            append(" AND ").append(MediaStore.Audio.Media.DURATION).append(" > 0")
        }
        try {
            activity.contentResolver.query(
                MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                projection,
                selection,
                arrayOf(sinceSec.toString()),
                "${MediaStore.Audio.Media.DATE_MODIFIED} DESC",
            )?.use { cursor ->
                val idIndex = cursor.getColumnIndex(MediaStore.Audio.Media._ID)
                val nameIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DISPLAY_NAME)
                val durationIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DURATION)
                val modifiedIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DATE_MODIFIED)
                val sizeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.SIZE)
                val mimeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.MIME_TYPE)
                while (cursor.moveToNext() && rows.size < limit) {
                    val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                    if (id <= 0L) continue
                    rows.add(
                        mapOf(
                            "id" to id,
                            "name" to if (nameIndex >= 0) cursor.getString(nameIndex) else null,
                            "durationMs" to if (durationIndex >= 0) {
                                cursor.getLong(durationIndex)
                            } else {
                                0L
                            },
                            "modifiedMs" to (
                                (if (modifiedIndex >= 0) cursor.getLong(modifiedIndex) else 0L) *
                                    1000L
                                ),
                            "size" to if (sizeIndex >= 0) cursor.getLong(sizeIndex) else 0L,
                            "mimeType" to if (mimeIndex >= 0) {
                                cursor.getString(mimeIndex)
                            } else {
                                null
                            },
                        ),
                    )
                }
            }
        } catch (_: Exception) {
            return emptyList()
        }
        return rows
    }

    private fun buildCapability(): Map<String, Any?> {
        val family = oemFamily()
        val audioPermission = hasAudioPermission()
        val recents = recentRecordings()
        val automaticSync = audioPermission && recents.isNotEmpty()
        val recorderPackages = installedRecorderPackages()
        val oemRecordingMayExist = family in setOf(
            "SAMSUNG", "VIVO", "OPPO", "REALME", "ONEPLUS", "XIAOMI", "HUAWEI",
            "HONOR", "MOTOROLA", "OTHER",
        )
        val capability = when {
            automaticSync -> "AUTOMATIC_MEDIASTORE"
            oemRecordingMayExist -> "MANUAL_IMPORT_ONLY"
            else -> "MANUAL_IMPORT_ONLY"
        }
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
            if (recents.isEmpty()) {
                add(
                    "No recent MediaStore recordings were found. If the OEM " +
                        "dialer records calls, its folder may be private; use " +
                        "manual import or the OEM recorder's share action."
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
        pendingPickResult = result
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "audio/*"
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        try {
            activity.startActivityForResult(
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
            pending.success(null)
            return true
        }
        try {
            activity.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        } catch (_: Exception) {
            // Not all providers grant persistable access; the cached copy
            // created below is still sufficient for this upload.
        }
        try {
            pending.success(copyRecordingToCache(uri, "SAF_IMPORT"))
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
        val toleranceMs = maxOf(6_000L, (callDurationMs * 0.15).toLong())
        val minModifiedSec = (startedAt - 120_000L) / 1000L
        val maxModifiedSec = (callEnd + 600_000L) / 1000L

        data class Candidate(
            val uri: Uri,
            val name: String,
            val durationMs: Long,
            val modifiedMs: Long,
            val size: Long,
            val mimeType: String,
        )

        val candidates = mutableListOf<Candidate>()
        val projection = arrayOf(
            MediaStore.Audio.Media._ID,
            MediaStore.Audio.Media.DISPLAY_NAME,
            MediaStore.Audio.Media.DURATION,
            MediaStore.Audio.Media.DATE_MODIFIED,
            MediaStore.Audio.Media.SIZE,
            MediaStore.Audio.Media.MIME_TYPE,
        )
        val selection = buildString {
            append(MediaStore.Audio.Media.IS_MUSIC).append(" = 0")
            append(" AND ").append(MediaStore.Audio.Media.DURATION).append(" > 0")
            append(" AND ").append(MediaStore.Audio.Media.DATE_MODIFIED).append(" >= ?")
            append(" AND ").append(MediaStore.Audio.Media.DATE_MODIFIED).append(" <= ?")
        }
        try {
            activity.contentResolver.query(
                MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                projection,
                selection,
                arrayOf(minModifiedSec.toString(), maxModifiedSec.toString()),
                "${MediaStore.Audio.Media.DATE_MODIFIED} DESC",
            )?.use { cursor ->
                val idIndex = cursor.getColumnIndex(MediaStore.Audio.Media._ID)
                val nameIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DISPLAY_NAME)
                val durationIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DURATION)
                val modifiedIndex = cursor.getColumnIndex(MediaStore.Audio.Media.DATE_MODIFIED)
                val sizeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.SIZE)
                val mimeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.MIME_TYPE)
                var inspected = 0
                while (cursor.moveToNext() && inspected < 200) {
                    inspected += 1
                    val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                    if (id <= 0L) continue
                    val size = if (sizeIndex >= 0) cursor.getLong(sizeIndex) else 0L
                    if (size < MIN_RECORDING_BYTES || size > MAX_RECORDING_BYTES) continue
                    val durationMs =
                        if (durationIndex >= 0) cursor.getLong(durationIndex) else 0L
                    if (durationMs <= 0L) continue
                    val modifiedMs =
                        (if (modifiedIndex >= 0) cursor.getLong(modifiedIndex) else 0L) * 1000L
                    val name =
                        (if (nameIndex >= 0) cursor.getString(nameIndex) else null)
                            .orEmpty()
                    val mime =
                        (if (mimeIndex >= 0) cursor.getString(mimeIndex) else null)
                            .orEmpty()

                    val durationDelta = kotlin.math.abs(durationMs - callDurationMs)
                    if (durationDelta > toleranceMs) continue

                    val nameDigits = name.replace(Regex("[^0-9]"), "")
                    val nameMatches = phoneKey.isNotBlank() && nameDigits.contains(phoneKey)
                    val timeClose = kotlin.math.abs(modifiedMs - callEnd) <= 120_000L
                    val exactDuration = durationDelta <= 3_000L
                    if (!nameMatches && !(exactDuration && timeClose)) continue

                    candidates.add(
                        Candidate(
                            uri = Uri.withAppendedPath(
                                MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                                id.toString(),
                            ),
                            name = name,
                            durationMs = durationMs,
                            modifiedMs = modifiedMs,
                            size = size,
                            mimeType = mime,
                        ),
                    )
                }
            }
        } catch (_: Exception) {
            result.success(null)
            return
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
            val copied = copyRecordingToCache(chosen.uri, "MEDIASTORE_MATCH")
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

    private fun copyRecordingToCache(uri: Uri, importSource: String): Map<String, Any?> {
        val resolver = activity.contentResolver
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

        val targetDir = File(activity.cacheDir, "call_recordings").apply { mkdirs() }
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
            retriever.setDataSource(activity, uri)
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
