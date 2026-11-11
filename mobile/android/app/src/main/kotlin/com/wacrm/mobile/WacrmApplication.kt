package com.wacrm.mobile

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.database.ContentObserver
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.CallLog

/**
 * Process-level setup for automatic call-log sync.
 *
 * WorkManager scheduling is harmless when the employee is logged out or sync
 * is not enabled; the worker checks both before starting a Flutter engine.
 * While this process is alive, a call-log ContentObserver requests a one-off
 * pass as soon as Android writes a finished call row.
 */
class WacrmApplication : Application() {

    private var callLogObserver: ContentObserver? = null

    override fun onCreate() {
        super.onCreate()
        AutomaticCallSyncScheduler.ensureScheduled(this)
        registerCallLogObserver()
    }

    private fun registerCallLogObserver() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M &&
            checkSelfPermission(Manifest.permission.READ_CALL_LOG) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        if (callLogObserver != null) return
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            private var lastScheduledAt = 0L

            override fun onChange(selfChange: Boolean, uri: android.net.Uri?) {
                val now = SystemClock.elapsedRealtime()
                // Android may emit several changes for one call (insert plus
                // metadata updates). Coalesce them into one debounced pass.
                if (now - lastScheduledAt < 15_000L) return
                lastScheduledAt = now
                AutomaticCallSyncScheduler.scheduleOneOff(
                    applicationContext,
                    delaySeconds = 5L,
                )
            }
        }
        try {
            contentResolver.registerContentObserver(
                CallLog.Calls.CONTENT_URI,
                true,
                observer,
            )
            callLogObserver = observer
        } catch (_: Exception) {
            // Without call-log access the periodic worker cannot run either.
        }
    }
}
