package com.wacrm.mobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager

/**
 * Call-end trigger that works while the app process is alive or started by the
 * system for the broadcast. Android 8+ may throttle implicit broadcasts on
 * some OEM builds, so this is a latency optimization, not the only scheduler:
 * the periodic WorkManager request and call-log ContentObserver cover it.
 */
class CallStateReceiver : BroadcastReceiver() {

    companion object {
        private const val PREFS = "wacrm_call_state"
        private const val KEY_SAW_CALL = "saw_call"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != TelephonyManager.ACTION_PHONE_STATE_CHANGED) return
        val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE) ?: return
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        when (state) {
            TelephonyManager.EXTRA_STATE_RINGING,
            TelephonyManager.EXTRA_STATE_OFFHOOK -> {
                prefs.edit().putBoolean(KEY_SAW_CALL, true).apply()
            }
            TelephonyManager.EXTRA_STATE_IDLE -> {
                if (!prefs.getBoolean(KEY_SAW_CALL, false)) return
                prefs.edit().putBoolean(KEY_SAW_CALL, false).apply()
                // Android writes the finished CallLog row just after IDLE.
                // A short delay keeps the first read from missing it.
                AutomaticCallSyncScheduler.scheduleOneOff(
                    context.applicationContext,
                    delaySeconds = 8L,
                )
            }
        }
    }
}
