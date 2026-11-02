package com.wacrm.mobile

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaMetadataRetriever
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.CallLog
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.provider.Settings
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.telephony.PhoneStateListener
import android.telephony.SubscriptionManager
import android.telephony.TelephonyCallback
import android.telephony.TelephonyManager
import android.util.Log
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Native Android SIM dialer.
 *
 * - Starts a real cellular call with ACTION_CALL, so the customer sees the
 *   employee's actual SIM caller ID (carrier-controlled).
 * - Lets the user choose a SIM on dual-SIM devices.
 * - Observes call state and, when READ_CALL_LOG is granted, reads the matching
 *   device call-log row for exact talk duration and final status.
 * - Sends the result back to Flutter, which syncs it through the existing
 *   manual-call CRM endpoint.
 *
 * No audio is captured. Android 10+ blocks third-party call recording and this
 * class intentionally contains no recording logic.
 */
class MobileSimCallManager(
    private val activity: Activity,
    messenger: BinaryMessenger,
) : MethodChannel.MethodCallHandler {

    companion object {
        private const val CHANNEL = "com.wacrm.mobile/sim_call"
        private const val TAG = "WACRM_CallDirection"
        private const val PERMISSION_REQUEST_CODE = 4917
        private const val PREFS = "wacrm_mobile_sim_call"
        private const val KEY_PENDING_RESULT = "pending_result"
        private const val KEY_ACTIVE_CALL = "active_call"
        private const val KEY_SHARED_RECORDING = "shared_recording"
        private const val FINALIZE_DELAY_MS = 1_200L
        private const val OFFHOOK_WATCHDOG_MS = 120_000L
        private const val STALE_ACTIVE_CALL_MS = 24 * 60 * 60 * 1000L
        private const val PICK_RECORDING_REQUEST_CODE = 4918
        private const val MAX_RECORDING_BYTES = 25L * 1024 * 1024
        private val RECORDING_EXTENSIONS = setOf(
            ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".amr",
            ".3gp", ".caf", ".webm", ".mp4",
        )
    }

    private val channel = MethodChannel(messenger, CHANNEL)
    private val handler = Handler(Looper.getMainLooper())
    private val prefs = activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private var pendingPermissionResult: MethodChannel.Result? = null
    private var pendingRecordingPickResult: MethodChannel.Result? = null
    private var mediaPlayer: MediaPlayer? = null
    private var playbackTimeout: Runnable? = null

    private var activeCall: ActiveCall? = null
    private var phoneStateListener: PhoneStateListener? = null
    private var telephonyCallback: Any? = null
    private var watchdogRunnable: Runnable? = null
    private var finalizeRunnable: Runnable? = null

    private data class ActiveCall(
        val callId: String,
        val phone: String,
        val leadId: Int?,
        val contactName: String?,
        val subscriptionId: Int?,
        val slotIndex: Int?,
        val simLabel: String?,
        val simPhoneNumber: String?,
        val startAt: Long,
        // Calls started by this manager are always outbound. Incoming device
        // calls are synced from CallLog, never tracked here.
        val direction: String = "OUTBOUND",
        var offhookAt: Long? = null,
        var endAt: Long? = null,
        var sawOffhook: Boolean = false,
        var sawRinging: Boolean = false,
        var finalized: Boolean = false,
    )

    private data class DeviceCallInfo(
        val id: Long,
        val date: Long,
        val duration: Int,
        val type: Int,
        val phoneAccountId: String?,
    )

    private data class RecordingCandidate(
        val uri: Uri,
        val name: String,
        val durationMs: Long,
        val modifiedMs: Long,
        val size: Long,
        val mimeType: String,
    )

    init {
        channel.setMethodCallHandler(this)
        recoverInterruptedCall()
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getCallPermissionStatus" -> result.success(permissionMap())
            "requestCallPermissions" -> requestCallPermissions(result)
            "getSimAccounts" -> getSimAccounts(result)
            "startCall" -> startCall(call, result)
            "openAppSettings" -> openAppSettings(result)
            "consumePendingResult" -> consumePendingResult(result)
            "clearPendingResult" -> clearPendingResult(call, result)
            "pickRecordingFile" -> pickRecordingFile(result)
            "consumeSharedRecordingFile" -> consumeSharedRecordingFile(result)
            "getRecentDeviceCalls" -> getRecentDeviceCalls(call, result)
            "getDeviceCallLogBaseline" -> getDeviceCallLogBaseline(result)
            "getDeviceCallsIncremental" -> getDeviceCallsIncremental(call, result)
            "findDeviceRecording" -> findDeviceRecording(call, result)
            "playRecording" -> playRecording(call, result)
            "stopRecordingPlayback" -> stopRecordingPlayback(result)
            else -> result.notImplemented()
        }
    }

    fun onRequestPermissionsResult(
        requestCode: Int,
        @Suppress("UNUSED_PARAMETER") permissions: Array<out String>,
        @Suppress("UNUSED_PARAMETER") grantResults: IntArray,
    ) {
        if (requestCode != PERMISSION_REQUEST_CODE) return
        val pending = pendingPermissionResult ?: return
        pendingPermissionResult = null
        pending.success(permissionMap())
    }

    fun dispose() {
        unregisterCallStateListener()
        cancelWatchdog()
        cancelFinalize()
        releaseMediaPlayer()
        handler.removeCallbacksAndMessages(null)
        channel.setMethodCallHandler(null)
        pendingPermissionResult = null
        pendingRecordingPickResult = null
    }

    /**
     * Receives the file selected in the system document picker. The file is
     * copied into the app cache immediately, so the returned content URI does
     * not have to stay readable for the lifetime of the upload.
     */
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        if (requestCode != PICK_RECORDING_REQUEST_CODE) return false
        val pending = pendingRecordingPickResult ?: return true
        pendingRecordingPickResult = null
        val uri = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null) {
            pending.success(null)
            return true
        }
        try {
            pending.success(copyRecordingToCache(uri))
        } catch (error: Exception) {
            pending.error("RECORDING_PICK_FAILED", error.message, null)
        }
        return true
    }

    /**
     * Handles "Share -> WACRM" from the OEM recorder / file manager. The shared
     * audio file is cached and offered to the user as an attachable recording.
     */
    @Suppress("DEPRECATION")
    fun handleShareIntent(intent: Intent?): Boolean {
        if (intent == null) return false
        val action = intent.action
        if (action != Intent.ACTION_SEND && action != Intent.ACTION_SEND_MULTIPLE) {
            return false
        }
        val uri: Uri? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (action == Intent.ACTION_SEND_MULTIPLE) {
                intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)?.firstOrNull()
            } else {
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            }
        } else {
            if (action == Intent.ACTION_SEND_MULTIPLE) {
                intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)?.firstOrNull()
            } else {
                intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
            }
        }
        if (uri == null) return false
        return try {
            val info = copyRecordingToCache(uri)
            prefs.edit()
                .putString(KEY_SHARED_RECORDING, JSONObject(info).toString())
                .apply()
            try {
                channel.invokeMethod("recordingShared", info)
            } catch (_: Exception) {
            }
            true
        } catch (_: Exception) {
            false
        }
    }

    // ------------------------------------------------------------------
    // Permissions
    // ------------------------------------------------------------------

    private fun requiredPermissions(): List<String> = listOf(
        Manifest.permission.CALL_PHONE,
        Manifest.permission.READ_PHONE_STATE,
    )

    private fun optionalPermissions(): List<String> = buildList {
        add(Manifest.permission.READ_CALL_LOG)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            add(Manifest.permission.READ_PHONE_NUMBERS)
        }
        // Read-only access to audio already produced by the OEM recorder.
        // WACRM never records calls itself.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.READ_MEDIA_AUDIO)
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
    }

    private fun hasMediaAudioPermission(): Boolean {
        return when {
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU ->
                hasPermission(Manifest.permission.READ_MEDIA_AUDIO)
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ->
                hasPermission(Manifest.permission.READ_EXTERNAL_STORAGE)
            else -> true
        }
    }

    private fun hasPermission(permission: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        return activity.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED
    }

    private fun permissionMap(): Map<String, Boolean> {
        return mapOf(
            "callPhone" to hasPermission(Manifest.permission.CALL_PHONE),
            "readPhoneState" to hasPermission(Manifest.permission.READ_PHONE_STATE),
            "readCallLog" to hasPermission(Manifest.permission.READ_CALL_LOG),
            "readMediaAudio" to hasMediaAudioPermission(),
            "readPhoneNumbers" to if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                hasPermission(Manifest.permission.READ_PHONE_NUMBERS)
            } else {
                true
            },
        )
    }

    private fun requestCallPermissions(result: MethodChannel.Result) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            result.success(permissionMap())
            return
        }
        val missing = (requiredPermissions() + optionalPermissions())
            .distinct()
            .filter { !hasPermission(it) }

        if (missing.isEmpty()) {
            result.success(permissionMap())
            return
        }
        if (pendingPermissionResult != null) {
            result.error("REQUEST_IN_PROGRESS", "A permission request is already open.", null)
            return
        }

        pendingPermissionResult = result
        activity.requestPermissions(missing.toTypedArray(), PERMISSION_REQUEST_CODE)
    }

    private fun openAppSettings(result: MethodChannel.Result) {
        try {
            val intent = Intent(
                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.fromParts("package", activity.packageName, null),
            ).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            activity.startActivity(intent)
            result.success(true)
        } catch (error: Exception) {
            result.error("SETTINGS_FAILED", error.message, null)
        }
    }

    // ------------------------------------------------------------------
    // Authorised recording import / playback
    // ------------------------------------------------------------------

    private fun pickRecordingFile(result: MethodChannel.Result) {
        if (pendingRecordingPickResult != null) {
            result.error("PICK_IN_PROGRESS", "A recording picker is already open.", null)
            return
        }
        pendingRecordingPickResult = result
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "audio/*"
            putExtra(
                Intent.EXTRA_MIME_TYPES,
                arrayOf(
                    "audio/mpeg", "audio/mp4", "audio/aac", "audio/wav",
                    "audio/ogg", "audio/opus", "audio/amr", "audio/3gpp",
                ),
            )
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        try {
            activity.startActivityForResult(intent, PICK_RECORDING_REQUEST_CODE)
        } catch (error: Exception) {
            pendingRecordingPickResult = null
            result.error("PICKER_UNAVAILABLE", error.message, null)
        }
    }

    private fun copyRecordingToCache(uri: Uri): Map<String, Any> {
        val resolver = activity.contentResolver
        var displayName = "recording"
        var reportedSize = -1L
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
                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) {
                    displayName = cursor.getString(nameIndex) ?: displayName
                }
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                    reportedSize = cursor.getLong(sizeIndex)
                }
            }
        }
        if (reportedSize > MAX_RECORDING_BYTES) {
            throw IllegalArgumentException("Recording is larger than the 25 MB limit.")
        }

        val mimeType = resolver.getType(uri).orEmpty()
        var extension = displayName.substringAfterLast('.', "").lowercase()
        if (extension.isNotEmpty()) extension = ".$extension"
        if (extension !in RECORDING_EXTENSIONS) {
            extension = extensionForMime(mimeType).orEmpty()
        }
        if (extension.isEmpty()) {
            throw IllegalArgumentException(
                "Unsupported recording format. Use MP3, M4A, AAC, WAV, OGG, " +
                    "OPUS, AMR, 3GP, CAF, WEBM or MP4.",
            )
        }

        val directory = File(activity.cacheDir, "recording_uploads").apply { mkdirs() }
        val safeBase = displayName
            .substringBeforeLast('.', displayName)
            .replace(Regex("[^A-Za-z0-9._-]"), "_")
            .take(40)
            .ifBlank { "recording" }
        val target = File(directory, "${System.currentTimeMillis()}_$safeBase$extension")

        var total = 0L
        try {
            val input = resolver.openInputStream(uri)
                ?: throw IllegalArgumentException("Could not read the selected file.")
            input.use { source ->
                FileOutputStream(target).use { output ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val read = source.read(buffer)
                        if (read <= 0) break
                        total += read
                        if (total > MAX_RECORDING_BYTES) {
                            throw IllegalArgumentException(
                                "Recording is larger than the 25 MB limit.",
                            )
                        }
                        output.write(buffer, 0, read)
                    }
                }
            }
        } catch (error: Exception) {
            target.delete()
            throw error
        }

        if (total < 1024) {
            target.delete()
            throw IllegalArgumentException("The selected file is empty or too small.")
        }

        val durationMs = try {
            verifyPlayableAudio(target)
        } catch (error: Exception) {
            target.delete()
            throw IllegalArgumentException(
                error.message ?: "The selected file is not a playable audio recording.",
            )
        }

        return mapOf(
            "path" to target.absolutePath,
            "name" to displayName,
            "size" to total,
            "mimeType" to mimeType,
            "durationMs" to durationMs,
        )
    }

    /**
     * Confirms the picked file decodes as audio before it is uploaded. A valid
     * extension alone is not enough: the CRM must never mark a call as recorded
     * because of a renamed or corrupt file.
     */
    private fun verifyPlayableAudio(file: File): Long {
        val retriever = MediaMetadataRetriever()
        try {
            retriever.setDataSource(file.absolutePath)
            val hasAudio = retriever.extractMetadata(
                MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO,
            )
            if (hasAudio != null && hasAudio.equals("no", ignoreCase = true)) {
                throw IllegalArgumentException("The selected file has no audio track.")
            }
            val duration = retriever.extractMetadata(
                MediaMetadataRetriever.METADATA_KEY_DURATION,
            )?.toLongOrNull() ?: 0L
            if (duration <= 0L) {
                throw IllegalArgumentException(
                    "The selected file could not be decoded as playable audio.",
                )
            }
            return duration
        } finally {
            try {
                retriever.release()
            } catch (_: Exception) {
            }
        }
    }

    private fun extensionForMime(mimeType: String): String? {
        return when (mimeType.substringBefore(';').trim().lowercase()) {
            "audio/mpeg", "audio/mp3" -> ".mp3"
            "audio/mp4", "audio/m4a", "audio/x-m4a" -> ".m4a"
            "audio/aac", "audio/x-aac" -> ".aac"
            "audio/wav", "audio/x-wav", "audio/wave" -> ".wav"
            "audio/ogg" -> ".ogg"
            "audio/opus" -> ".opus"
            "audio/amr" -> ".amr"
            "audio/3gpp", "video/3gpp", "audio/3gpp2" -> ".3gp"
            "audio/caf", "audio/x-caf" -> ".caf"
            "audio/webm" -> ".webm"
            else -> null
        }
    }

    private fun consumeSharedRecordingFile(result: MethodChannel.Result) {
        val raw = prefs.getString(KEY_SHARED_RECORDING, null)
        if (raw.isNullOrBlank()) {
            result.success(null)
            return
        }
        prefs.edit().remove(KEY_SHARED_RECORDING).apply()
        try {
            val json = JSONObject(raw)
            val path = json.optString("path")
            val file = File(path)
            if (!file.isFile) {
                result.success(null)
                return
            }
            result.success(
                mapOf(
                    "path" to file.absolutePath,
                    "name" to json.optString("name", file.name),
                    "size" to file.length(),
                    "mimeType" to json.optString("mimeType", "audio/*"),
                ),
            )
        } catch (_: Exception) {
            result.success(null)
        }
    }

    private fun playRecording(call: MethodCall, result: MethodChannel.Result) {
        val url = call.argument<String>("url")?.trim().orEmpty()
        if (url.isEmpty()) {
            result.error("INVALID_URL", "A recording URL is required.", null)
            return
        }
        val token = call.argument<String>("token")
        releaseMediaPlayer()

        var finished = false
        fun complete(errorCode: String? = null, message: String? = null) {
            if (finished) return
            finished = true
            playbackTimeout?.let { handler.removeCallbacks(it) }
            playbackTimeout = null
            if (errorCode != null) {
                result.error(errorCode, message, null)
            } else {
                result.success(true)
            }
        }

        try {
            val player = MediaPlayer()
            mediaPlayer = player
            // Managed /uploads/ files are public static assets; sending an
            // Authorization header to them makes some Samsung media stacks
            // fail the HTTP request. External PBX URLs keep the header.
            val isManagedUpload = Uri.parse(url).path.orEmpty().let { path ->
                path.contains("/uploads/") || path.contains("/media/recordings/")
            }
            val headers = if (token.isNullOrBlank() || isManagedUpload) {
                emptyMap()
            } else {
                mapOf("Authorization" to "Bearer $token")
            }
            player.setDataSource(activity, Uri.parse(url), headers)
            player.setOnPreparedListener {
                it.start()
                complete()
            }
            player.setOnCompletionListener { releaseMediaPlayer() }
            player.setOnErrorListener { _, what, extra ->
                releaseMediaPlayer()
                // Report the real HTTP failure (404/405/403...) instead of an
                // opaque Android media code. This runs off the UI thread.
                Thread {
                    val probe = probeRecordingUrl(url, headers)
                    complete(
                        "PLAYBACK_FAILED",
                        "Unable to play this recording ($what/$extra)$probe",
                    )
                }.start()
                true
            }
            player.prepareAsync()

            val timeout = Runnable {
                releaseMediaPlayer()
                complete("PLAYBACK_TIMEOUT", "Recording playback timed out.")
            }
            playbackTimeout = timeout
            handler.postDelayed(timeout, 20_000L)
        } catch (error: Exception) {
            releaseMediaPlayer()
            complete("PLAYBACK_FAILED", error.message ?: "Unable to play recording.")
        }
    }

    private fun stopRecordingPlayback(result: MethodChannel.Result) {
        releaseMediaPlayer()
        result.success(true)
    }

    /**
     * Best-effort HTTP probe used only after MediaPlayer fails, so the user and
     * support see a real status code instead of an opaque media error.
     */
    private fun probeRecordingUrl(url: String, headers: Map<String, String>): String {
        return try {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 8_000
                readTimeout = 8_000
                requestMethod = "GET"
                setRequestProperty("Range", "bytes=0-0")
                headers.forEach { (key, value) -> setRequestProperty(key, value) }
            }
            val code = connection.responseCode
            val type = connection.contentType.orEmpty()
            connection.disconnect()
            buildString {
                append("; HTTP ")
                append(code)
                if (type.isNotBlank()) {
                    append(", ")
                    append(type)
                }
            }
        } catch (error: Exception) {
            "; ${error.javaClass.simpleName}: ${error.message.orEmpty()}"
        }
    }

    private fun releaseMediaPlayer() {
        playbackTimeout?.let { handler.removeCallbacks(it) }
        playbackTimeout = null
        mediaPlayer?.let { player ->
            try {
                if (player.isPlaying) player.stop()
            } catch (_: Exception) {
            }
            try {
                player.reset()
            } catch (_: Exception) {
            }
            try {
                player.release()
            } catch (_: Exception) {
            }
        }
        mediaPlayer = null
    }

    // ------------------------------------------------------------------
    // SIM discovery
    // ------------------------------------------------------------------

    private fun getSimAccounts(result: MethodChannel.Result) {
        if (!hasPermission(Manifest.permission.READ_PHONE_STATE)) {
            result.error(
                "PERMISSION_DENIED",
                "Phone state permission is required to read SIM information.",
                null,
            )
            return
        }

        try {
            val infos = activeSubscriptionInfos()
            if (infos.isEmpty()) {
                result.success(emptyList<Map<String, Any?>>())
                return
            }

            val defaultSubId = try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                    SubscriptionManager.getDefaultVoiceSubscriptionId()
                } else {
                    -1
                }
            } catch (_: Exception) {
                -1
            }

            val accounts = infos.map { info ->
                val number = try {
                    if (hasPermission(Manifest.permission.READ_PHONE_NUMBERS)) {
                        info.number?.takeIf { it.isNotBlank() }
                    } else {
                        null
                    }
                } catch (_: Exception) {
                    null
                }
                val handle = findPhoneAccountHandleForSubscription(info.subscriptionId)

                mapOf<String, Any?>(
                    "subscriptionId" to info.subscriptionId,
                    "slotIndex" to info.simSlotIndex,
                    "carrierName" to (info.carrierName?.toString() ?: ""),
                    "displayName" to (info.displayName?.toString() ?: ""),
                    "phoneNumber" to number,
                    "isDefault" to (info.subscriptionId == defaultSubId),
                    "phoneAccountId" to handle?.id,
                    "phoneAccountComponent" to handle?.componentName?.flattenToString(),
                    "simFingerprint" to simFingerprint(info, handle, number),
                    "isEmbedded" to (
                        Build.VERSION.SDK_INT >= Build.VERSION_CODES.P &&
                            info.isEmbedded
                        ),
                )
            }.sortedBy { (it["slotIndex"] as? Int) ?: 0 }

            result.success(accounts)
        } catch (error: Exception) {
            result.error("SIM_READ_FAILED", error.message, null)
        }
    }

    private fun activeSubscriptionInfos() = try {
        val manager = activity.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE)
            as? SubscriptionManager
        manager?.activeSubscriptionInfoList ?: emptyList()
    } catch (_: SecurityException) {
        emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    private fun telecomManager(): TelecomManager? =
        activity.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager

    private fun telephonyManager(): TelephonyManager? =
        activity.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager

    /**
     * Resolves a phone account to its subscription using only public Android
     * APIs. Below Android 11 no public API exposes this, so callers fall back to
     * the phone-account identity instead of guessing from the slot.
     */
    private fun resolveSubscriptionIdForHandle(handle: PhoneAccountHandle?): Int? {
        if (handle == null) return null
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        return try {
            telephonyManager()?.getSubscriptionId(handle)?.takeIf {
                it != SubscriptionManager.INVALID_SUBSCRIPTION_ID
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun findPhoneAccountHandleForSubscription(subscriptionId: Int?): PhoneAccountHandle? {
        if (subscriptionId == null) return null
        return try {
            telecomManager()?.callCapablePhoneAccounts?.firstOrNull { handle ->
                resolveSubscriptionIdForHandle(handle) == subscriptionId
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun findPhoneAccountHandleForCall(
        accountId: String?,
        component: String?,
    ): PhoneAccountHandle? {
        val handles = try {
            telecomManager()?.callCapablePhoneAccounts ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
        val componentName = component
            ?.takeIf { it.isNotBlank() }
            ?.let { ComponentName.unflattenFromString(it) }
        return when {
            componentName != null && !accountId.isNullOrBlank() ->
                handles.firstOrNull {
                    it.componentName == componentName && it.id == accountId
                }
            componentName != null -> handles.firstOrNull { it.componentName == componentName }
            !accountId.isNullOrBlank() -> handles.firstOrNull { it.id == accountId }
            else -> null
        }
    }

    private fun simFingerprint(
        info: android.telephony.SubscriptionInfo?,
        handle: PhoneAccountHandle?,
        number: String?,
    ): String {
        val raw = listOf(
            info?.subscriptionId?.toString() ?: "",
            info?.simSlotIndex?.toString() ?: "",
            info?.carrierName?.toString() ?: "",
            info?.displayName?.toString() ?: "",
            number.orEmpty(),
            handle?.id ?: "",
            handle?.componentName?.flattenToString() ?: "",
        ).joinToString("|")
        return try {
            MessageDigest.getInstance("SHA-256")
                .digest(raw.toByteArray())
                .joinToString("") { "%02x".format(it) }
        } catch (_: Exception) {
            raw.hashCode().toUInt().toString(16)
        }
    }

    private fun resolveSubscriptionIdForCall(
        accountId: String?,
        component: String?,
    ): Int? {
        if (accountId.isNullOrBlank() && component.isNullOrBlank()) return null
        val handle = findPhoneAccountHandleForCall(accountId, component)
        return resolveSubscriptionIdForHandle(handle)
    }

    // ------------------------------------------------------------------
    // Call start
    // ------------------------------------------------------------------

    private fun startCall(call: MethodCall, result: MethodChannel.Result) {
        val phone = sanitizeDialNumber(call.argument<String>("phone").orEmpty())
        if (phone.replace("+", "").length < 3) {
            result.error(
                "INVALID_NUMBER",
                "Enter a valid phone number with at least 3 digits.",
                null,
            )
            return
        }
        if (!hasPermission(Manifest.permission.CALL_PHONE)) {
            result.error("PERMISSION_DENIED", "Call permission has not been granted.", null)
            return
        }
        if (activeCall != null) {
            result.error("CALL_IN_PROGRESS", "A device call is already being tracked.", null)
            return
        }

        val callId = call.argument<String>("callId")?.trim().orEmpty()
        if (callId.isEmpty()) {
            result.error("INVALID_CALL_ID", "A client call id is required.", null)
            return
        }

        val current = ActiveCall(
            callId = callId,
            phone = phone,
            leadId = (call.argument<Number>("leadId"))?.toInt(),
            contactName = call.argument<String>("contactName"),
            subscriptionId = (call.argument<Number>("subscriptionId"))?.toInt(),
            slotIndex = (call.argument<Number>("slotIndex"))?.toInt(),
            simLabel = call.argument<String>("simLabel"),
            simPhoneNumber = call.argument<String>("simPhoneNumber"),
            startAt = System.currentTimeMillis(),
        )

        activeCall = current
        saveActiveCall(current)
        registerCallStateListener()
        scheduleWatchdog(current)

        try {
            val intent = Intent(Intent.ACTION_CALL, Uri.fromParts("tel", phone, null)).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

                // OEM fallbacks used by several dual-SIM dialers.
                current.slotIndex?.let { slot ->
                    putExtra("com.android.phone.extra.slot", slot)
                    putExtra("simSlot", slot)
                    putExtra("slot", slot)
                }
                current.subscriptionId?.let { subId ->
                    putExtra("subscription", subId)
                    putExtra("subId", subId)
                }

                // AOSP way to target a phone account (API 26+). Resolved only on
                // API 30+, where TelephonyManager exposes the subscription id.
                resolvePhoneAccountForSubscription(current.subscriptionId)?.let { handle ->
                    putExtra(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, handle)
                }
            }

            activity.startActivity(intent)
            result.success(
                mapOf(
                    "success" to true,
                    "callId" to callId,
                    "subscriptionId" to current.subscriptionId,
                ),
            )
        } catch (error: Exception) {
            activeCall = null
            clearActiveCall()
            unregisterCallStateListener()
            cancelWatchdog()
            result.error("CALL_FAILED", error.message ?: "Unable to start the call.", null)
        }
    }

    private fun resolvePhoneAccountForSubscription(subscriptionId: Int?): PhoneAccountHandle? {
        if (subscriptionId == null || Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
            return null
        }
        return try {
            val telecom = activity.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager
            val telephony = activity.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
            if (telecom == null || telephony == null) return null

            telecom.callCapablePhoneAccounts.firstOrNull { handle ->
                try {
                    telephony.getSubscriptionId(handle) == subscriptionId
                } catch (_: Exception) {
                    false
                }
            }
        } catch (_: Exception) {
            null
        }
    }

    // ------------------------------------------------------------------
    // Call state tracking
    // ------------------------------------------------------------------

    private fun registerCallStateListener() {
        unregisterCallStateListener()
        val telephony = activity.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
            ?: return

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val callback = object : TelephonyCallback(), TelephonyCallback.CallStateListener {
                    override fun onCallStateChanged(state: Int) {
                        handleCallState(state)
                    }
                }
                telephony.registerTelephonyCallback(activity.mainExecutor, callback)
                telephonyCallback = callback
            } else {
                @Suppress("DEPRECATION")
                val listener = object : PhoneStateListener() {
                    @Deprecated("Deprecated in Java")
                    override fun onCallStateChanged(state: Int, phoneNumber: String?) {
                        handleCallState(state)
                    }
                }
                @Suppress("DEPRECATION")
                telephony.listen(listener, PhoneStateListener.LISTEN_CALL_STATE)
                phoneStateListener = listener
            }
        } catch (_: Exception) {
            // Without phone-state access the call can still be placed; duration
            // will be logged as unavailable/estimated when it returns.
            telephonyCallback = null
            phoneStateListener = null
        }
    }

    @Suppress("DEPRECATION")
    private fun unregisterCallStateListener() {
        val telephony = activity.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                (telephonyCallback as? TelephonyCallback)?.let { callback ->
                    telephony?.unregisterTelephonyCallback(callback)
                }
            } else {
                phoneStateListener?.let { listener ->
                    telephony?.listen(listener, PhoneStateListener.LISTEN_NONE)
                }
            }
        } catch (_: Exception) {
            // Listener may already be detached.
        }
        telephonyCallback = null
        phoneStateListener = null
    }

    private fun handleCallState(state: Int) {
        val current = activeCall ?: return
        if (current.finalized) return

        when (state) {
            TelephonyManager.CALL_STATE_RINGING -> {
                current.sawRinging = true
            }

            TelephonyManager.CALL_STATE_OFFHOOK -> {
                current.sawOffhook = true
                if (current.offhookAt == null) {
                    current.offhookAt = System.currentTimeMillis()
                }
                cancelWatchdog()
            }

            TelephonyManager.CALL_STATE_IDLE -> {
                // Registration emits the current IDLE state before dialing starts.
                // Only finalize after we have seen the call become active.
                if (current.sawOffhook || current.sawRinging) {
                    if (!current.finalized) {
                        current.finalized = true
                        current.endAt = System.currentTimeMillis()
                        scheduleFinalize(current)
                    }
                }
            }
        }
    }

    private fun scheduleWatchdog(current: ActiveCall) {
        cancelWatchdog()
        val runnable = Runnable {
            if (activeCall === current && !current.finalized) {
                val liveState = try {
                    (activity.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager)?.callState
                } catch (_: Exception) {
                    null
                }
                if (liveState != null && liveState != TelephonyManager.CALL_STATE_IDLE) {
                    // The device never emitted OFFHOOK but the call is still live.
                    scheduleWatchdog(current)
                    return@Runnable
                }
                current.finalized = true
                current.endAt = System.currentTimeMillis()
                unregisterCallStateListener()
                finalizeCall(current)
            }
        }
        watchdogRunnable = runnable
        handler.postDelayed(runnable, OFFHOOK_WATCHDOG_MS)
    }

    private fun cancelWatchdog() {
        watchdogRunnable?.let { handler.removeCallbacks(it) }
        watchdogRunnable = null
    }

    private fun scheduleFinalize(current: ActiveCall) {
        unregisterCallStateListener()
        cancelWatchdog()
        cancelFinalize()

        val runnable = Runnable {
            if (activeCall === current) {
                finalizeCall(current)
            }
        }
        finalizeRunnable = runnable
        // Android writes the device call-log row shortly after the call ends.
        handler.postDelayed(runnable, FINALIZE_DELAY_MS)
    }

    private fun cancelFinalize() {
        finalizeRunnable?.let { handler.removeCallbacks(it) }
        finalizeRunnable = null
    }

    private fun finalizeCall(current: ActiveCall) {
        if (activeCall !== current) return
        activeCall = null
        clearActiveCall()
        cancelWatchdog()
        cancelFinalize()
        unregisterCallStateListener()

        val resultMap = buildCallResult(current)
        savePendingResult(resultMap)
        try {
            channel.invokeMethod("onCallEnded", resultMap)
        } catch (_: Exception) {
            // Flutter not attached; the pending result is synced on next launch.
        }
    }

    // ------------------------------------------------------------------
    // Device call log (duration + status)
    // ------------------------------------------------------------------

    @SuppressLint("MissingPermission")
    private fun queryDeviceCallLog(current: ActiveCall): DeviceCallInfo? {
        if (!hasPermission(Manifest.permission.READ_CALL_LOG)) return null

        val since = current.startAt - 5_000L
        val projection = arrayOf(
            CallLog.Calls._ID,
            CallLog.Calls.DATE,
            CallLog.Calls.DURATION,
            CallLog.Calls.TYPE,
            CallLog.Calls.NUMBER,
            CallLog.Calls.PHONE_ACCOUNT_ID,
        )

        return try {
            activity.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                projection,
                "${CallLog.Calls.DATE} >= ?",
                arrayOf(since.toString()),
                "${CallLog.Calls.DATE} DESC",
            )?.use { cursor ->
                val idIndex = cursor.getColumnIndex(CallLog.Calls._ID)
                val dateIndex = cursor.getColumnIndex(CallLog.Calls.DATE)
                val durationIndex = cursor.getColumnIndex(CallLog.Calls.DURATION)
                val typeIndex = cursor.getColumnIndex(CallLog.Calls.TYPE)
                val numberIndex = cursor.getColumnIndex(CallLog.Calls.NUMBER)
                val accountIndex = cursor.getColumnIndex(CallLog.Calls.PHONE_ACCOUNT_ID)

                var inspected = 0
                while (cursor.moveToNext() && inspected < 15) {
                    inspected += 1
                    val number = if (numberIndex >= 0) cursor.getString(numberIndex) else null
                    if (!numbersMatch(number, current.phone)) continue

                    val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                    val date = if (dateIndex >= 0) cursor.getLong(dateIndex) else current.startAt
                    // The device row must belong to this attempt, not an older
                    // call to the same number. Allow a small clock skew window.
                    if (date > 0 && date < current.startAt - 30_000L) continue
                    val duration = if (durationIndex >= 0) cursor.getInt(durationIndex) else 0
                    val type = if (typeIndex >= 0) cursor.getInt(typeIndex) else 0
                    val accountId = if (accountIndex >= 0) cursor.getString(accountIndex) else null
                    return DeviceCallInfo(id, date, duration, type, accountId)
                }
                null
            }
        } catch (_: Exception) {
            null
        }
    }

    // ------------------------------------------------------------------
    // Native call-history synchronization
    // ------------------------------------------------------------------

    private fun androidId(): String {
        return try {
            Settings.Secure.getString(
                activity.contentResolver,
                Settings.Secure.ANDROID_ID,
            ).orEmpty()
        } catch (_: Exception) {
            ""
        }
    }

    private fun nativeReferenceFor(callLogId: Long): String? {
        if (callLogId <= 0L) return null
        val device = androidId().ifBlank { "device" }
        return "MOBILE_${device}_${callLogId}".take(100)
    }

    /**
     * The one and only Android call-type -> CRM direction mapping.
     *
     * Mirrors android.provider.CallLog.Calls.TYPE. Returns null for types the
     * CRM does not support (voicemail, unknown), so callers skip the row rather
     * than guessing a direction.
     */
    private fun callDirectionForType(type: Int): String? = when (type) {
        CallLog.Calls.OUTGOING_TYPE -> "OUTBOUND"
        CallLog.Calls.INCOMING_TYPE,
        CallLog.Calls.MISSED_TYPE,
        CallLog.Calls.REJECTED_TYPE,
        CallLog.Calls.BLOCKED_TYPE,
        CallLog.Calls.ANSWERED_EXTERNALLY_TYPE -> "INBOUND"
        else -> null
    }

    /**
     * Returns recent device call-log rows (incoming, outgoing and missed) so
     * the CRM can synchronize SIM history automatically. Only telephony rows
     * are returned: VoIP/SIP accounts and WACRM's own connection service are
     * excluded so a DooCTI/WebRTC call can never be re-labelled as MOBILE.
     */
    @SuppressLint("MissingPermission")
    private fun getRecentDeviceCalls(call: MethodCall, result: MethodChannel.Result) {
        if (!hasPermission(Manifest.permission.READ_CALL_LOG)) {
            result.error(
                "PERMISSION_DENIED",
                "Call-log access has not been granted.",
                null,
            )
            return
        }
        val since = call.argument<Number>("sinceMillis")?.toLong()
            ?: (System.currentTimeMillis() - 24L * 60 * 60 * 1000)
        val limit = (call.argument<Number>("limit")?.toInt() ?: 200)
            .coerceIn(1, 500)

        val projection = arrayOf(
            CallLog.Calls._ID,
            CallLog.Calls.DATE,
            CallLog.Calls.DURATION,
            CallLog.Calls.TYPE,
            CallLog.Calls.NUMBER,
            CallLog.Calls.PHONE_ACCOUNT_ID,
            CallLog.Calls.PHONE_ACCOUNT_COMPONENT_NAME,
            CallLog.Calls.CACHED_NAME,
        )

        try {
            val rows = mutableListOf<Map<String, Any?>>()
            val activeSubs = activeSubscriptionInfos()
            activity.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                projection,
                "${CallLog.Calls.DATE} >= ?",
                arrayOf(since.toString()),
                "${CallLog.Calls.DATE} DESC",
            )?.use { cursor ->
                val idIndex = cursor.getColumnIndex(CallLog.Calls._ID)
                val dateIndex = cursor.getColumnIndex(CallLog.Calls.DATE)
                val durationIndex = cursor.getColumnIndex(CallLog.Calls.DURATION)
                val typeIndex = cursor.getColumnIndex(CallLog.Calls.TYPE)
                val numberIndex = cursor.getColumnIndex(CallLog.Calls.NUMBER)
                val accountIndex = cursor.getColumnIndex(CallLog.Calls.PHONE_ACCOUNT_ID)
                val componentIndex =
                    cursor.getColumnIndex(CallLog.Calls.PHONE_ACCOUNT_COMPONENT_NAME)
                val nameIndex = cursor.getColumnIndex(CallLog.Calls.CACHED_NAME)

                while (cursor.moveToNext() && rows.size < limit) {
                    val type = if (typeIndex >= 0) cursor.getInt(typeIndex) else 0
                    // Android's CallLog.Calls.TYPE is the single source of truth
                    // for direction. Never infer it from phone numbers, duration
                    // or recording metadata.
                    val direction = callDirectionForType(type) ?: continue
                    val component =
                        if (componentIndex >= 0) cursor.getString(componentIndex) else null
                    val account =
                        if (accountIndex >= 0) cursor.getString(accountIndex) else null
                    if (!isTelephonyCall(component, account)) continue

                    val number =
                        (if (numberIndex >= 0) cursor.getString(numberIndex) else null)
                            ?.trim()
                            .orEmpty()
                    if (number.isBlank()) continue

                    val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                    val nativeRef = nativeReferenceFor(id) ?: continue
                    val date = if (dateIndex >= 0) cursor.getLong(dateIndex) else 0L
                    val duration = if (durationIndex >= 0) {
                        cursor.getInt(durationIndex).coerceAtLeast(0)
                    } else {
                        0
                    }
                    val status = when (type) {
                        CallLog.Calls.MISSED_TYPE -> "MISSED"
                        CallLog.Calls.REJECTED_TYPE,
                        CallLog.Calls.BLOCKED_TYPE -> "REJECTED"
                        else -> when {
                            duration > 0 -> "COMPLETED"
                            direction == "OUTBOUND" -> "NO_ANSWER"
                            else -> "MISSED"
                        }
                    }
                    val resolvedSubscriptionId = resolveSubscriptionIdForCall(account, component)
                    val subscriptionInfo = resolvedSubscriptionId?.let { subId ->
                        activeSubs.firstOrNull { it.subscriptionId == subId }
                    }
                    val simIdentity = when {
                        resolvedSubscriptionId != null -> "subId:$resolvedSubscriptionId"
                        !account.isNullOrBlank() && !component.isNullOrBlank() ->
                            "phoneAccount:$component#$account"
                        !account.isNullOrBlank() -> "phoneAccount:$account"
                        else -> null
                    }
                    val simIdentityStatus = when {
                        resolvedSubscriptionId != null -> "RESOLVED"
                        !account.isNullOrBlank() -> "PHONE_ACCOUNT_ONLY"
                        else -> "MISSING"
                    }
                    // Temporary direction diagnostics. No phone number, audio or
                    // personal call content is logged.
                    Log.d(
                        TAG,
                        "history id=$id type=$type account=${account ?: "-"} " +
                            "component=${component ?: "-"} subId=${resolvedSubscriptionId ?: "-"} " +
                            "nativeDirection=$direction identity=${simIdentity ?: "-"} " +
                            "identityStatus=$simIdentityStatus",
                    )
                    rows.add(
                        mapOf(
                            "nativeCallReference" to nativeRef,
                            "deviceCallLogId" to id,
                            "phone" to number,
                            "direction" to direction,
                            "type" to type,
                            "status" to status,
                            "dateMillis" to date,
                            "durationSeconds" to if (status == "COMPLETED") duration else 0,
                            "startedAt" to isoUtc(date),
                            "endedAt" to isoUtc(
                                if (duration > 0) date + duration * 1000L else date,
                            ),
                            "simAccountId" to account?.takeIf { it.isNotBlank() },
                            "simAccountComponent" to component?.takeIf { it.isNotBlank() },
                            "simSubscriptionId" to resolvedSubscriptionId,
                            "simSlotIndex" to subscriptionInfo?.simSlotIndex,
                            "simCarrierName" to subscriptionInfo?.carrierName?.toString(),
                            "simIdentity" to simIdentity,
                            "simIdentityStatus" to simIdentityStatus,
                            "contactName" to (
                                if (nameIndex >= 0) cursor.getString(nameIndex) else null
                                )?.takeIf { it.isNotBlank() },
                        ),
                    )
                }
            }
            result.success(rows)
        } catch (error: Exception) {
            result.error("CALL_LOG_READ_FAILED", error.message, null)
        }
    }

    /**
     * Returns the newest Android call-log row so the CRM can establish an
     * incremental-sync baseline without importing any history. Uses the whole
     * telephony call log, not the filtered CRM subset.
     */
    @SuppressLint("MissingPermission")
    private fun getDeviceCallLogBaseline(result: MethodChannel.Result) {
        if (!hasPermission(Manifest.permission.READ_CALL_LOG)) {
            result.error(
                "PERMISSION_DENIED",
                "Call-log access has not been granted.",
                null,
            )
            return
        }
        val projection = arrayOf(CallLog.Calls._ID, CallLog.Calls.DATE)
        try {
            activity.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                projection,
                null,
                null,
                "${CallLog.Calls.DATE} DESC, ${CallLog.Calls._ID} DESC",
            )?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val idIndex = cursor.getColumnIndex(CallLog.Calls._ID)
                    val dateIndex = cursor.getColumnIndex(CallLog.Calls.DATE)
                    val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                    val date = if (dateIndex >= 0) cursor.getLong(dateIndex) else 0L
                    result.success(
                        mapOf(
                            "dateMillis" to date.coerceAtLeast(0L),
                            "callLogId" to id.coerceAtLeast(0L),
                        ),
                    )
                    return
                }
            }
            result.success(mapOf("dateMillis" to 0L, "callLogId" to 0L))
        } catch (error: Exception) {
            result.error("CALL_LOG_READ_FAILED", error.message, null)
        }
    }

    /**
     * Returns call-log rows strictly after the composite (DATE, _ID) cursor in
     * ascending order. The optional grace window re-reads recent rows so a
     * delayed Android insert is not missed; callers dedupe by native reference.
     */
    @SuppressLint("MissingPermission")
    private fun getDeviceCallsIncremental(call: MethodCall, result: MethodChannel.Result) {
        if (!hasPermission(Manifest.permission.READ_CALL_LOG)) {
            result.error(
                "PERMISSION_DENIED",
                "Call-log access has not been granted.",
                null,
            )
            return
        }
        val afterDate = (call.argument<Number>("afterDateMillis")?.toLong() ?: 0L)
            .coerceAtLeast(0L)
        val afterId = (call.argument<Number>("afterId")?.toLong() ?: 0L)
            .coerceAtLeast(0L)
        val grace = (call.argument<Number>("graceMillis")?.toLong() ?: 0L)
            .coerceAtLeast(0L)
        val limit = (call.argument<Number>("limit")?.toInt() ?: 250)
            .coerceIn(1, 500)
        val lower = (afterDate - grace).coerceAtLeast(0L)

        val projection = arrayOf(
            CallLog.Calls._ID,
            CallLog.Calls.DATE,
            CallLog.Calls.DURATION,
            CallLog.Calls.TYPE,
            CallLog.Calls.NUMBER,
            CallLog.Calls.PHONE_ACCOUNT_ID,
            CallLog.Calls.PHONE_ACCOUNT_COMPONENT_NAME,
            CallLog.Calls.CACHED_NAME,
        )

        try {
            val rows = mutableListOf<Map<String, Any?>>()
            val activeSubs = activeSubscriptionInfos()
            activity.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                projection,
                "${CallLog.Calls.DATE} >= ?",
                arrayOf(lower.toString()),
                "${CallLog.Calls.DATE} ASC, ${CallLog.Calls._ID} ASC",
            )?.use { cursor ->
                val idIndex = cursor.getColumnIndex(CallLog.Calls._ID)
                val dateIndex = cursor.getColumnIndex(CallLog.Calls.DATE)
                val durationIndex = cursor.getColumnIndex(CallLog.Calls.DURATION)
                val typeIndex = cursor.getColumnIndex(CallLog.Calls.TYPE)
                val numberIndex = cursor.getColumnIndex(CallLog.Calls.NUMBER)
                val accountIndex = cursor.getColumnIndex(CallLog.Calls.PHONE_ACCOUNT_ID)
                val componentIndex =
                    cursor.getColumnIndex(CallLog.Calls.PHONE_ACCOUNT_COMPONENT_NAME)
                val nameIndex = cursor.getColumnIndex(CallLog.Calls.CACHED_NAME)

                while (cursor.moveToNext() && rows.size < limit) {
                    val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                    val date = if (dateIndex >= 0) cursor.getLong(dateIndex) else 0L
                    if (grace > 0L) {
                        if (date < lower) continue
                    } else if (
                        date < afterDate ||
                        (date == afterDate && id <= afterId)
                    ) {
                        continue
                    }
                    val type = if (typeIndex >= 0) cursor.getInt(typeIndex) else 0
                    val direction = callDirectionForType(type) ?: continue
                    val component =
                        if (componentIndex >= 0) cursor.getString(componentIndex) else null
                    val account =
                        if (accountIndex >= 0) cursor.getString(accountIndex) else null
                    if (!isTelephonyCall(component, account)) continue

                    val number =
                        (if (numberIndex >= 0) cursor.getString(numberIndex) else null)
                            ?.trim()
                            .orEmpty()
                    if (number.isBlank()) continue

                    val nativeRef = nativeReferenceFor(id) ?: continue
                    val duration = if (durationIndex >= 0) {
                        cursor.getInt(durationIndex).coerceAtLeast(0)
                    } else {
                        0
                    }
                    val status = when (type) {
                        CallLog.Calls.MISSED_TYPE -> "MISSED"
                        CallLog.Calls.REJECTED_TYPE,
                        CallLog.Calls.BLOCKED_TYPE -> "REJECTED"
                        else -> when {
                            duration > 0 -> "COMPLETED"
                            direction == "OUTBOUND" -> "NO_ANSWER"
                            else -> "MISSED"
                        }
                    }
                    val resolvedSubscriptionId = resolveSubscriptionIdForCall(account, component)
                    val subscriptionInfo = resolvedSubscriptionId?.let { subId ->
                        activeSubs.firstOrNull { it.subscriptionId == subId }
                    }
                    val simIdentity = when {
                        resolvedSubscriptionId != null -> "subId:$resolvedSubscriptionId"
                        !account.isNullOrBlank() && !component.isNullOrBlank() ->
                            "phoneAccount:$component#$account"
                        !account.isNullOrBlank() -> "phoneAccount:$account"
                        else -> null
                    }
                    val simIdentityStatus = when {
                        resolvedSubscriptionId != null -> "RESOLVED"
                        !account.isNullOrBlank() -> "PHONE_ACCOUNT_ONLY"
                        else -> "MISSING"
                    }
                    rows.add(
                        mapOf(
                            "nativeCallReference" to nativeRef,
                            "deviceCallLogId" to id,
                            "phone" to number,
                            "direction" to direction,
                            "type" to type,
                            "status" to status,
                            "dateMillis" to date,
                            "durationSeconds" to if (status == "COMPLETED") duration else 0,
                            "startedAt" to isoUtc(date),
                            "endedAt" to isoUtc(
                                if (duration > 0) date + duration * 1000L else date,
                            ),
                            "simAccountId" to account?.takeIf { it.isNotBlank() },
                            "simAccountComponent" to component?.takeIf { it.isNotBlank() },
                            "simSubscriptionId" to resolvedSubscriptionId,
                            "simSlotIndex" to subscriptionInfo?.simSlotIndex,
                            "simCarrierName" to subscriptionInfo?.carrierName?.toString(),
                            "simIdentity" to simIdentity,
                            "simIdentityStatus" to simIdentityStatus,
                            "contactName" to (
                                if (nameIndex >= 0) cursor.getString(nameIndex) else null
                                )?.takeIf { it.isNotBlank() },
                        ),
                    )
                }
            }
            result.success(
                mapOf(
                    "rows" to rows,
                    "hasMore" to (rows.size >= limit),
                ),
            )
        } catch (error: Exception) {
            result.error("CALL_LOG_READ_FAILED", error.message, null)
        }
    }

    /**
     * SIP/VoIP and WACRM's own connection service rows are not SIM calls.
     * Everything else is the device's real cellular call log.
     */
    private fun isTelephonyCall(component: String?, accountId: String?): Boolean {
        val marker = "${component.orEmpty()} ${accountId.orEmpty()}".lowercase()
        if (marker.isBlank()) return true
        if (marker.contains("com.wacrm.mobile")) return false
        if (marker.contains("sip") || marker.contains("voip")) return false
        if (marker.contains("webrtc")) return false
        return true
    }

    // ------------------------------------------------------------------
    // Device recording discovery (read-only, opt-in)
    // ------------------------------------------------------------------

    /**
     * Looks for exactly one existing audio file that can be attributed to the
     * given native call. If zero or more than one candidate matches, nothing is
     * returned: the CRM must show "Recording Unavailable" rather than attach
     * another call's audio. WACRM never records audio itself.
     */
    private fun findDeviceRecording(call: MethodCall, result: MethodChannel.Result) {
        val phone = call.argument<String>("phone").orEmpty()
        val startedAt = call.argument<Number>("startedAtMillis")?.toLong() ?: 0L
        val endedAt = call.argument<Number>("endedAtMillis")?.toLong() ?: 0L
        val durationSeconds = call.argument<Number>("durationSeconds")?.toInt() ?: 0
        if (phone.isBlank() || durationSeconds <= 0 || startedAt <= 0L) {
            result.success(null)
            return
        }
        if (!hasMediaAudioPermission()) {
            result.success(null)
            return
        }

        val callDurationMs = durationSeconds * 1000L
        val callEnd = if (endedAt > 0L) endedAt else startedAt + callDurationMs
        val phoneDigits = phone.replace(Regex("[^0-9]"), "")
        val phoneKey = phoneDigits.takeLast(10)
        val toleranceMs = maxOf(6_000L, (callDurationMs * 0.15).toLong())
        val minModifiedSec = (startedAt - 120_000L) / 1000L
        val maxModifiedSec = (callEnd + 600_000L) / 1000L

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
            val candidates = mutableListOf<RecordingCandidate>()
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
                val modifiedIndex =
                    cursor.getColumnIndex(MediaStore.Audio.Media.DATE_MODIFIED)
                val sizeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.SIZE)
                val mimeIndex = cursor.getColumnIndex(MediaStore.Audio.Media.MIME_TYPE)

                var inspected = 0
                while (cursor.moveToNext() && inspected < 200) {
                    inspected += 1
                    val id = if (idIndex >= 0) cursor.getLong(idIndex) else 0L
                    if (id <= 0L) continue
                    val size = if (sizeIndex >= 0) cursor.getLong(sizeIndex) else 0L
                    if (size < 1024L || size > MAX_RECORDING_BYTES) continue
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
                    val nameMatches =
                        phoneKey.isNotBlank() && nameDigits.contains(phoneKey)
                    val timeClose = kotlin.math.abs(modifiedMs - callEnd) <= 120_000L
                    val exactDuration = durationDelta <= 3_000L
                    if (!nameMatches && !(exactDuration && timeClose)) continue

                    val uri = Uri.withAppendedPath(
                        MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                        id.toString(),
                    )
                    candidates.add(
                        RecordingCandidate(uri, name, durationMs, modifiedMs, size, mime),
                    )
                }
            }

            // Ambiguity is never resolved by guessing.
            if (candidates.size != 1) {
                result.success(null)
                return
            }
            val chosen = candidates.first()
            if (!chosen.mimeType.startsWith("audio/") && chosen.mimeType.isNotBlank()) {
                result.success(null)
                return
            }
            val copied = copyRecordingToCache(chosen.uri)
            result.success(
                copied + mapOf(
                    "source" to "DEVICE",
                    "matchedBy" to if (
                        chosen.name.replace(Regex("[^0-9]"), "").contains(phoneKey)
                    ) {
                        "filename"
                    } else {
                        "duration_and_time"
                    },
                ),
            )
        } catch (_: Exception) {
            // MediaStore is not readable on this device/format; degrade to
            // "Recording Unavailable" rather than risk a wrong attachment.
            result.success(null)
        }
    }

    // ------------------------------------------------------------------
    // Dial number normalization
    // ------------------------------------------------------------------

    /**
     * Converts a CRM-stored number into a dial-safe string. Leads are often
     * saved as "+91 98765 43210" or "+91-98765-43210"; ACTION_CALL rejects
     * spaces and separators, which surfaced as "Invalid phone number".
     * Keeps one leading '+', digits, and USSD '*'/'#' characters.
     */
    private fun sanitizeDialNumber(raw: String): String {
        val trimmed = raw.trim()
        if (trimmed.isEmpty()) return ""

        val builder = StringBuilder()
        for ((index, ch) in trimmed.withIndex()) {
            val digit = Character.digit(ch, 10)
            when {
                digit >= 0 -> builder.append(('0'.code + digit).toChar())
                ch == '*' || ch == '#' -> builder.append(ch)
                ch == '+' && index == 0 -> builder.append(ch)
            }
        }

        var value = builder.toString()
        if (value.startsWith("00")) {
            value = "+" + value.substring(2)
        }
        return value
    }

    private fun numbersMatch(deviceNumber: String?, customerNumber: String): Boolean {
        val device = deviceNumber?.replace(Regex("[^0-9]"), "").orEmpty()
        val customer = customerNumber.replace(Regex("[^0-9]"), "")
        if (device.isEmpty() || customer.isEmpty()) return false
        if (device == customer) return true
        if (device.length < 7 || customer.length < 7) return false
        return device.takeLast(10) == customer.takeLast(10)
    }

    private fun buildCallResult(current: ActiveCall): Map<String, Any?> {
        val deviceLog = queryDeviceCallLog(current)
        // Prefer the native call-log row's TYPE (authoritative). If the device
        // exposes a type the CRM does not understand, mark the direction
        // UNKNOWN so Flutter can refuse to synchronize it. Never fall back to
        // OUTBOUND merely because the type is missing/unsupported.
        val direction = when {
            deviceLog != null -> callDirectionForType(deviceLog.type) ?: "UNKNOWN"
            else -> current.direction
        }
        val endAt = current.endAt ?: System.currentTimeMillis()
        val startedAt: Long
        var durationSeconds: Int
        var status: String
        var durationAccuracy: String

        if (deviceLog != null) {
            durationAccuracy = "exact"
            startedAt = if (deviceLog.date > 0) deviceLog.date else current.startAt
            durationSeconds = deviceLog.duration.coerceAtLeast(0)
            status = when {
                deviceLog.type == CallLog.Calls.MISSED_TYPE -> "MISSED"
                deviceLog.type == CallLog.Calls.REJECTED_TYPE ||
                    deviceLog.type == CallLog.Calls.BLOCKED_TYPE -> "REJECTED"
                durationSeconds > 0 -> "COMPLETED"
                direction == "OUTBOUND" -> "NO_ANSWER"
                else -> "FAILED"
            }
        } else {
            durationAccuracy = "estimated"
            startedAt = current.startAt
            val activeFrom = current.offhookAt ?: current.startAt
            durationSeconds = ((endAt - activeFrom) / 1000L).toInt().coerceAtLeast(0)
            status = when {
                // OFFHOOK is the only signal that proves the call connected.
                current.sawOffhook && durationSeconds > 0 -> "COMPLETED"
                current.sawOffhook -> "ANSWERED"
                current.sawRinging -> "NO_ANSWER"
                else -> "FAILED"
            }
        }

        if (status != "COMPLETED" && status != "ANSWERED") {
            durationSeconds = 0
        }

        val answeredAt = if (durationSeconds > 0) endAt - durationSeconds * 1000L else null
        val simIdentity = current.subscriptionId?.let { "subId:$it" }
            ?: deviceLog?.phoneAccountId?.takeIf { it.isNotBlank() }
                ?.let { "phoneAccount:$it" }
        val simAccountId = simIdentity
            ?: deviceLog?.phoneAccountId?.takeIf { it.isNotBlank() }
        val simIdentityStatus = when {
            current.subscriptionId != null -> "RESOLVED"
            !deviceLog?.phoneAccountId.isNullOrBlank() -> "PHONE_ACCOUNT_ONLY"
            else -> "MISSING"
        }
        val simLabel = current.simLabel?.takeIf { it.isNotBlank() }
            ?: current.slotIndex?.let { "SIM ${it + 1}" }

        return mapOf(
            "callId" to current.callId,
            "callReference" to current.callId,
            "deviceCallLogId" to deviceLog?.id?.takeIf { it > 0L },
            "nativeCallReference" to deviceLog?.id?.let { nativeReferenceFor(it) },
            "leadId" to current.leadId,
            "customerPhone" to current.phone,
            "contactName" to current.contactName,
            "callDirection" to direction,
            "callType" to deviceLog?.type,
            "callStatus" to status,
            "durationSeconds" to durationSeconds,
            "durationAccuracy" to durationAccuracy,
            "startedAt" to isoUtc(startedAt),
            "answeredAt" to isoUtc(answeredAt),
            "endedAt" to isoUtc(endAt),
            "simAccountId" to simAccountId,
            "simSubscriptionId" to current.subscriptionId,
            "simIdentity" to simIdentity,
            "simIdentityStatus" to simIdentityStatus,
            "simLabel" to simLabel,
            "simSlot" to current.slotIndex,
            "simPhoneNumber" to current.simPhoneNumber,
            // The app never records calls. Device/carrier recordings are not
            // exposed through a public Android API.
            "recordingUrl" to null,
            "recordingStatus" to "RECORDING_UNAVAILABLE",
            "source" to "MOBILE_SIM",
        )
    }

    private fun isoUtc(millis: Long?): String? {
        if (millis == null || millis <= 0) return null
        return try {
            val formatter = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
            formatter.timeZone = TimeZone.getTimeZone("UTC")
            formatter.format(Date(millis))
        } catch (_: Exception) {
            null
        }
    }

    // ------------------------------------------------------------------
    // Pending result persistence (survives app background / process death)
    // ------------------------------------------------------------------

    private fun saveActiveCall(current: ActiveCall) {
        try {
            val json = JSONObject().apply {
                put("callId", current.callId)
                put("phone", current.phone)
                current.leadId?.let { put("leadId", it) }
                current.contactName?.let { put("contactName", it) }
                current.subscriptionId?.let { put("subscriptionId", it) }
                current.slotIndex?.let { put("slotIndex", it) }
                current.simLabel?.let { put("simLabel", it) }
                current.simPhoneNumber?.let { put("simPhoneNumber", it) }
                put("startAt", current.startAt)
            }
            prefs.edit().putString(KEY_ACTIVE_CALL, json.toString()).apply()
        } catch (_: Exception) {
            // Persistence is best-effort.
        }
    }

    private fun clearActiveCall() {
        prefs.edit().remove(KEY_ACTIVE_CALL).apply()
    }

    private fun savePendingResult(map: Map<String, Any?>) {
        try {
            val json = JSONObject()
            map.forEach { (key, value) ->
                if (value != null) json.put(key, value)
            }
            prefs.edit().putString(KEY_PENDING_RESULT, json.toString()).apply()
        } catch (_: Exception) {
            // Persistence is best-effort; the live event still reaches Flutter.
        }
    }

    private fun consumePendingResult(result: MethodChannel.Result) {
        val raw = prefs.getString(KEY_PENDING_RESULT, null)
        if (raw.isNullOrBlank()) {
            result.success(null)
            return
        }
        try {
            result.success(jsonToMap(JSONObject(raw)))
        } catch (_: Exception) {
            prefs.edit().remove(KEY_PENDING_RESULT).apply()
            result.success(null)
        }
    }

    private fun clearPendingResult(call: MethodCall, result: MethodChannel.Result) {
        val callId = call.argument<String>("callId")
        val raw = prefs.getString(KEY_PENDING_RESULT, null)
        if (raw.isNullOrBlank()) {
            result.success(true)
            return
        }
        try {
            val storedCallId = JSONObject(raw).optString("callId", "")
            if (callId.isNullOrBlank() || callId == storedCallId) {
                prefs.edit().remove(KEY_PENDING_RESULT).apply()
            }
        } catch (_: Exception) {
            prefs.edit().remove(KEY_PENDING_RESULT).apply()
        }
        result.success(true)
    }

    private fun jsonToMap(json: JSONObject): Map<String, Any?> {
        val map = mutableMapOf<String, Any?>()
        val keys = json.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val value = json.get(key)
            if (value != JSONObject.NULL) map[key] = value
        }
        return map
    }

    /**
     * If the process was killed during a call, the active-call marker survives.
     * When call-log access is available, reconstruct the result from the device
     * call log and leave it for Flutter to sync on the next launch.
     */
    private fun recoverInterruptedCall() {
        val raw = prefs.getString(KEY_ACTIVE_CALL, null) ?: return
        try {
            val json = JSONObject(raw)
            val startAt = json.optLong("startAt", 0L)
            val callId = json.optString("callId", "")
            if (callId.isEmpty() || startAt <= 0L) {
                clearActiveCall()
                return
            }
            if (System.currentTimeMillis() - startAt > STALE_ACTIVE_CALL_MS) {
                clearActiveCall()
                return
            }
            // A completed result already exists; do not overwrite it.
            if (!prefs.getString(KEY_PENDING_RESULT, null).isNullOrBlank()) {
                clearActiveCall()
                return
            }

            val current = ActiveCall(
                callId = callId,
                phone = json.optString("phone", ""),
                leadId = if (json.has("leadId")) json.optInt("leadId") else null,
                contactName = json.optString("contactName", "").takeIf { it.isNotBlank() },
                subscriptionId = if (json.has("subscriptionId")) json.optInt("subscriptionId") else null,
                slotIndex = if (json.has("slotIndex")) json.optInt("slotIndex") else null,
                simLabel = json.optString("simLabel", "").takeIf { it.isNotBlank() },
                simPhoneNumber = json.optString("simPhoneNumber", "").takeIf { it.isNotBlank() },
                startAt = startAt,
                // Recovery after process death has no live telephony evidence.
                // Only a matching device call-log row may prove the call
                // connected; otherwise the attempt stays unverified.
                offhookAt = null,
                sawOffhook = false,
            )

            val deviceLog = queryDeviceCallLog(current)
            if (deviceLog == null) {
                // Without READ_CALL_LOG we cannot recover a duration. Mark the
                // attempt unverified (FAILED), never COMPLETED, once the phone
                // is idle and the call is safely over.
                val callState = try {
                    (activity.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager)?.callState
                } catch (_: Exception) {
                    null
                }
                if (
                    callState != null &&
                    callState == TelephonyManager.CALL_STATE_IDLE &&
                    System.currentTimeMillis() - startAt >= 5 * 60 * 1000L
                ) {
                    current.endAt = System.currentTimeMillis()
                    current.finalized = true
                    savePendingResult(buildCallResult(current))
                    clearActiveCall()
                }
                return
            }
            if (deviceLog.duration <= 0 && deviceLog.type == CallLog.Calls.OUTGOING_TYPE) {
                // A zero-duration outgoing call is a completed attempt, not a
                // finished conversation; leave it for the live flow if possible.
                current.endAt = deviceLog.date
            } else {
                current.endAt = deviceLog.date + deviceLog.duration * 1000L
            }
            current.sawOffhook = deviceLog.duration > 0
            current.finalized = true

            val resultMap = buildCallResult(current)
            savePendingResult(resultMap)
            clearActiveCall()
        } catch (_: Exception) {
            // Keep the marker for a later attempt; it expires after 24 hours.
        }
    }
}
