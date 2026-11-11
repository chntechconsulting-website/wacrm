import 'dart:ui' show DartPluginRegistrant;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app.dart';
import 'core/services/automatic_call_sync_service.dart';

/// Entry point used by the native WorkManager worker when the app UI is not
/// running. It must stay a top-level function and be annotated so AOT builds
/// keep it reachable.
@pragma('vm:entry-point')
Future<void> backgroundCallSyncMain() async {
  WidgetsFlutterBinding.ensureInitialized();
  // A background isolate does not inherit the main isolate's Dart plugin
  // registrations. shared_preferences (server URL/token and the pending queue)
  // needs its federated Dart implementation registered here.
  DartPluginRegistrant.ensureInitialized();
  await AutomaticCallSyncService.runBackgroundSync();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Set preferred mobile portrait orientations & system UI overlay style
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarColor: Colors.white,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
  );

  runApp(const WaCrmApp());
}
