package com.wacrm.mobile

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.CallLog
import android.provider.Settings
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.telephony.PhoneStateListener
import android.telephony.SubscriptionManager
import android.telephony.TelephonyCallback
import android.telephony.TelephonyManager
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
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
        private const val PERMISSION_REQUEST_CODE = 4917
        private const val PREFS = "wacrm_mobile_sim_call"
        private const val KEY_PENDING_RESULT = "pending_result"
        private const val KEY_ACTIVE_CALL = "active_call"
        private const val FINALIZE_DELAY_MS = 1_200L
        private const val OFFHOOK_WATCHDOG_MS = 120_000L
        private const val STALE_ACTIVE_CALL_MS = 24 * 60 * 60 * 1000L
    }

    private val channel = MethodChannel(messenger, CHANNEL)
    private val handler = Handler(Looper.getMainLooper())
    private val prefs = activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private var pendingPermissionResult: MethodChannel.Result? = null

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
        var offhookAt: Long? = null,
        var endAt: Long? = null,
        var sawOffhook: Boolean = false,
        var sawRinging: Boolean = false,
        var finalized: Boolean = false,
    )

    private data class DeviceCallInfo(
        val date: Long,
        val duration: Int,
        val type: Int,
        val phoneAccountId: String?,
    )

    init {
        channel.setMethodCallHandler(this)
        recoverInterruptedCall()
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "requestCallPermissions" -> requestCallPermissions(result)
            "getSimAccounts" -> getSimAccounts(result)
            "startCall" -> startCall(call, result)
            "openAppSettings" -> openAppSettings(result)
            "consumePendingResult" -> consumePendingResult(result)
            "clearPendingResult" -> clearPendingResult(call, result)
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
        handler.removeCallbacksAndMessages(null)
        channel.setMethodCallHandler(null)
        pendingPermissionResult = null
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
            val manager = activity.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE)
                as? SubscriptionManager
            if (manager == null) {
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

            val infos = try {
                manager.activeSubscriptionInfoList ?: emptyList()
            } catch (_: SecurityException) {
                emptyList()
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

                mapOf<String, Any?>(
                    "subscriptionId" to info.subscriptionId,
                    "slotIndex" to info.simSlotIndex,
                    "carrierName" to (info.carrierName?.toString() ?: ""),
                    "displayName" to (info.displayName?.toString() ?: ""),
                    "phoneNumber" to number,
                    "isDefault" to (info.subscriptionId == defaultSubId),
                )
            }.sortedBy { (it["slotIndex"] as? Int) ?: 0 }

            result.success(accounts)
        } catch (error: Exception) {
            result.error("SIM_READ_FAILED", error.message, null)
        }
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

        val since = current.startAt - 2_000L
        val projection = arrayOf(
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

                    val date = if (dateIndex >= 0) cursor.getLong(dateIndex) else current.startAt
                    val duration = if (durationIndex >= 0) cursor.getInt(durationIndex) else 0
                    val type = if (typeIndex >= 0) cursor.getInt(typeIndex) else 0
                    val accountId = if (accountIndex >= 0) cursor.getString(accountIndex) else null
                    return DeviceCallInfo(date, duration, type, accountId)
                }
                null
            }
        } catch (_: Exception) {
            null
        }
    }

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
                deviceLog.type == CallLog.Calls.REJECTED_TYPE -> "REJECTED"
                durationSeconds > 0 -> "COMPLETED"
                else -> "NO_ANSWER"
            }
        } else {
            durationAccuracy = "estimated"
            startedAt = current.startAt
            val activeFrom = current.offhookAt ?: current.startAt
            durationSeconds = ((endAt - activeFrom) / 1000L).toInt().coerceAtLeast(0)
            status = if (current.sawOffhook && durationSeconds > 0) "COMPLETED" else "NO_ANSWER"
        }

        if (status != "COMPLETED" && status != "ANSWERED") {
            durationSeconds = 0
        }

        val answeredAt = if (durationSeconds > 0) endAt - durationSeconds * 1000L else null
        val simAccountId = deviceLog?.phoneAccountId?.takeIf { it.isNotBlank() }
            ?: current.subscriptionId?.let { "subId:$it" }
        val simLabel = current.simLabel?.takeIf { it.isNotBlank() }
            ?: current.slotIndex?.let { "SIM ${it + 1}" }

        return mapOf(
            "callId" to current.callId,
            "leadId" to current.leadId,
            "customerPhone" to current.phone,
            "contactName" to current.contactName,
            "callDirection" to "OUTBOUND",
            "callStatus" to status,
            "durationSeconds" to durationSeconds,
            "durationAccuracy" to durationAccuracy,
            "startedAt" to isoUtc(startedAt),
            "answeredAt" to isoUtc(answeredAt),
            "endedAt" to isoUtc(endAt),
            "simAccountId" to simAccountId,
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
                offhookAt = startAt,
                sawOffhook = true,
            )

            val deviceLog = queryDeviceCallLog(current) ?: return
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
