package com.wacrm.mobile

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.work.Worker
import androidx.work.WorkerParameters
import io.flutter.FlutterInjector
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.dart.DartExecutor
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * Headless WorkManager worker that runs the exact Dart pipeline used by the
 * manual Sync button.
 *
 * The worker never uploads call logs itself: it starts a Flutter engine,
 * registers [BackgroundCallLogBridge] on the same channel as the UI, and waits
 * for the Dart entrypoint to report its outcome. WorkManager then retries
 * transient failures with backoff while the Dart queue keeps unsynced calls.
 */
class AutomaticCallSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : Worker(appContext, params) {

    companion object {
        private const val TAG = "WACRM_AutoSync"
        private const val BACKGROUND_CHANNEL =
            "com.wacrm.mobile/background_call_sync"
        private const val DART_ENTRYPOINT = "backgroundCallSyncMain"
        private const val TIMEOUT_SECONDS = 480L
    }

    private data class SyncOutcome(
        val success: Boolean,
        val retry: Boolean,
        val error: String?,
    )

    override fun doWork(): Result {
        val context = applicationContext
        if (!hasCallLogPermission(context)) {
            Log.i(TAG, "Skipping background sync: READ_CALL_LOG is not granted.")
            return Result.success()
        }
        if (!hasStoredSession(context)) {
            Log.i(TAG, "Skipping background sync: no authenticated session.")
            return Result.success()
        }

        val completion = CountDownLatch(1)
        val destroyed = CountDownLatch(1)
        val mainHandler = Handler(Looper.getMainLooper())
        val engineRef = AtomicReference<FlutterEngine?>(null)
        val outcomeRef = AtomicReference(
            SyncOutcome(success = false, retry = true, error = "NO_RESULT"),
        )

        mainHandler.post {
            try {
                val engine = FlutterEngine(context)
                engineRef.set(engine)
                BackgroundCallLogBridge(context, engine.dartExecutor.binaryMessenger)
                MethodChannel(
                    engine.dartExecutor.binaryMessenger,
                    BACKGROUND_CHANNEL,
                ).setMethodCallHandler { call, result ->
                    if (call.method == "syncFinished") {
                        val arguments = call.arguments
                        val map = arguments as? Map<*, *>
                        outcomeRef.set(
                            SyncOutcome(
                                success = map?.get("success") == true,
                                retry = map?.get("retry") == true,
                                error = map?.get("error")?.toString(),
                            ),
                        )
                        result.success(null)
                        completion.countDown()
                    } else {
                        result.notImplemented()
                    }
                }

                val loader = FlutterInjector.instance().flutterLoader()
                val bundlePath = loader.findAppBundlePath()
                engine.dartExecutor.executeDartEntrypoint(
                    DartExecutor.DartEntrypoint(bundlePath, DART_ENTRYPOINT),
                )
            } catch (error: Throwable) {
                Log.e(TAG, "Unable to start the background sync engine.", error)
                outcomeRef.set(
                    SyncOutcome(
                        success = false,
                        retry = true,
                        error = error.message,
                    ),
                )
                completion.countDown()
            }
        }

        val finished = try {
            completion.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
            false
        }

        mainHandler.post {
            try {
                engineRef.get()?.destroy()
            } catch (error: Throwable) {
                Log.w(TAG, "Background engine did not shut down cleanly.", error)
            }
            destroyed.countDown()
        }
        destroyed.await(5, TimeUnit.SECONDS)

        val outcome = outcomeRef.get()
        if (!finished) {
            Log.w(TAG, "Background sync timed out; WorkManager will retry.")
            return Result.retry()
        }
        if (outcome.retry) {
            Log.i(
                TAG,
                "Background sync needs retry: ${outcome.error ?: "pending queue"}",
            )
            return Result.retry()
        }
        Log.i(
            TAG,
            "Background sync finished (success=${outcome.success}).",
        )
        return Result.success()
    }

    private fun hasCallLogPermission(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        return context.checkSelfPermission(Manifest.permission.READ_CALL_LOG) ==
            PackageManager.PERMISSION_GRANTED
    }

    /**
     * Reads the same legacy SharedPreferences store used by TokenStorage.
     * This avoids booting a Flutter engine every 15 minutes while logged out.
     */
    private fun hasStoredSession(context: Context): Boolean {
        val prefs = context.getSharedPreferences(
            "FlutterSharedPreferences",
            Context.MODE_PRIVATE,
        )
        val token = prefs.getString("flutter.crm_token", null)
        val user = prefs.getString("flutter.crm_user", null)
        return !token.isNullOrBlank() && !user.isNullOrBlank()
    }
}
