package com.wacrm.mobile

import android.content.Intent
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    private var mobileSimCallManager: MobileSimCallManager? = null
    private var mobileCallRecordingManager: MobileCallRecordingManager? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        mobileSimCallManager = MobileSimCallManager(this, flutterEngine.dartExecutor.binaryMessenger)
        mobileCallRecordingManager =
            MobileCallRecordingManager(this, flutterEngine.dartExecutor.binaryMessenger)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Cold start from "Share -> WACRM" while the app was not running.
        mobileSimCallManager?.handleShareIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        // Warm start from "Share -> WACRM" while the app is already open.
        mobileSimCallManager?.handleShareIntent(intent)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val handledByRecorder =
            mobileCallRecordingManager?.onActivityResult(requestCode, resultCode, data) == true
        if (!handledByRecorder) {
            mobileSimCallManager?.onActivityResult(requestCode, resultCode, data)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        mobileSimCallManager?.onRequestPermissionsResult(requestCode, permissions, grantResults)
    }

    override fun onDestroy() {
        mobileCallRecordingManager?.dispose()
        mobileCallRecordingManager = null
        mobileSimCallManager?.dispose()
        mobileSimCallManager = null
        super.onDestroy()
    }
}
