package com.wacrm.mobile

import android.Manifest
import android.annotation.SuppressLint
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.provider.CallLog
import android.provider.Settings
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.telephony.SubscriptionManager
import android.telephony.TelephonyManager
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Read-only call-log/SIM bridge for the headless background sync engine.
 *
 * The channel name and response maps are intentionally identical to
 * MobileSimCallManager so OfficeSyncService.evaluate() and
 * DeviceCallLogSyncService see exactly the same SIM identity and call rows in
 * the UI and in WorkManager. This class never starts calls, records audio or
 * registers listeners.
 */
class BackgroundCallLogBridge(
    private val context: Context,
    messenger: BinaryMessenger,
) : MethodChannel.MethodCallHandler {

    companion object {
        const val CHANNEL = "com.wacrm.mobile/sim_call"
    }

    private val channel = MethodChannel(messenger, CHANNEL)

    init {
        channel.setMethodCallHandler(this)
    }

    fun dispose() {
        channel.setMethodCallHandler(null)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getCallPermissionStatus" -> result.success(permissionMap())
            "getSimAccounts" -> getSimAccounts(result)
            "getDeviceCallLogBaseline" -> getDeviceCallLogBaseline(result)
            "getDeviceCallsIncremental" -> getDeviceCallsIncremental(call, result)
            else -> result.notImplemented()
        }
    }

    // ------------------------------------------------------------------
    // Permissions
    // ------------------------------------------------------------------

    private fun hasPermission(permission: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        return context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED
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

    // ------------------------------------------------------------------
    // SIM discovery (must match MobileSimCallManager exactly)
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
        val manager = context.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE)
            as? SubscriptionManager
        manager?.activeSubscriptionInfoList ?: emptyList()
    } catch (_: SecurityException) {
        emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    private fun telecomManager(): TelecomManager? =
        context.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager

    private fun telephonyManager(): TelephonyManager? =
        context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager

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
    // Call-log reads
    // ------------------------------------------------------------------

    private fun androidId(): String {
        return try {
            Settings.Secure.getString(
                context.contentResolver,
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

    private fun callDirectionForType(type: Int): String? = when (type) {
        CallLog.Calls.OUTGOING_TYPE -> "OUTBOUND"
        CallLog.Calls.INCOMING_TYPE,
        CallLog.Calls.MISSED_TYPE,
        CallLog.Calls.REJECTED_TYPE,
        CallLog.Calls.BLOCKED_TYPE,
        CallLog.Calls.ANSWERED_EXTERNALLY_TYPE -> "INBOUND"
        else -> null
    }

    private fun isTelephonyCall(component: String?, accountId: String?): Boolean {
        val marker = "${component.orEmpty()} ${accountId.orEmpty()}".lowercase()
        if (marker.isBlank()) return true
        if (marker.contains("com.wacrm.mobile")) return false
        if (marker.contains("sip") || marker.contains("voip")) return false
        if (marker.contains("webrtc")) return false
        return true
    }

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
            context.contentResolver.query(
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
     * delayed Android insert is not missed; the Dart queue dedupes by native
     * reference.
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
            context.contentResolver.query(
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
}
