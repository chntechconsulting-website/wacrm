package com.wacrm.mobile

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * Owns the persistent WorkManager schedule for mobile call-log sync.
 *
 * A periodic 15-minute request is the safety net. Call-state broadcasts and
 * call-log content changes request a one-off pass for near-real-time delivery.
 * WorkManager persists both across process death and normal reboots.
 */
object AutomaticCallSyncScheduler {
    const val PERIODIC_WORK = "wacrm_periodic_call_log_sync"
    const val ONE_OFF_WORK = "wacrm_call_log_sync_now"

    private const val TAG = "wacrm-call-sync"
    private const val PERIOD_MINUTES = 15L

    fun ensureScheduled(context: Context) {
        try {
            val constraints = Constraints.Builder()
                // Local call metadata is durable in Android's call log even
                // while offline; waiting for connectivity avoids booting the
                // engine only to fail immediately.
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request =
                PeriodicWorkRequestBuilder<AutomaticCallSyncWorker>(
                    PERIOD_MINUTES,
                    TimeUnit.MINUTES,
                )
                    .setConstraints(constraints)
                    .setBackoffCriteria(
                        BackoffPolicy.EXPONENTIAL,
                        30,
                        TimeUnit.SECONDS,
                    )
                    .addTag(TAG)
                    .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_WORK,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
        } catch (_: Exception) {
            // WorkManager is unavailable only in unusual restricted builds;
            // the in-app manual Sync button remains functional.
        }
    }

    fun scheduleOneOff(context: Context, delaySeconds: Long = 5L) {
        try {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request = OneTimeWorkRequestBuilder<AutomaticCallSyncWorker>()
                .setConstraints(constraints)
                .setInitialDelay(
                    delaySeconds.coerceAtLeast(0L),
                    TimeUnit.SECONDS,
                )
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    30,
                    TimeUnit.SECONDS,
                )
                .addTag(TAG)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                ONE_OFF_WORK,
                // APPEND_OR_REPLACE keeps the pass that is already running and
                // queues one follow-up for the newest call-log change.
                ExistingWorkPolicy.APPEND_OR_REPLACE,
                request,
            )
        } catch (_: Exception) {
            // The periodic request will pick the call up later.
        }
    }
}
