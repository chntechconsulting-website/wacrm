package com.wacrm.mobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Restores the periodic schedule after reboot or an app update. WorkManager
 * normally persists its own work, but re-enqueueing the unique request is
 * idempotent and protects against OEM cleanup.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED -> {
                AutomaticCallSyncScheduler.ensureScheduled(context.applicationContext)
            }
        }
    }
}
