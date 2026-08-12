import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'behavior/station_geofence_service.dart';
import 'design/root_shell.dart';
import 'design/theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Android-only target: no explicit FirebaseOptions needed - the
  // google-services.json-driven Gradle plugin supplies them. See
  // push_registration_service.dart for what this app actually uses
  // Firebase for (just FCM tokens/push, nothing else).
  await Firebase.initializeApp();
  await _initBackgroundGeofencingIfEnabled();
  runApp(const CommuteOSApp());
}

/// Re-initializes native_geofence and re-syncs the geofence set on every
/// cold start, but ONLY if the user has already opted in via
/// PreferencesScreen's toggle (see StationGeofenceService's docs) - the
/// toggle's own on/off action is what does this the FIRST time; this is
/// what makes it durable across app restarts/device reboots without
/// requiring the user to revisit that screen. Never itself requests any
/// permission or turns anything on - a user who never opted in sees zero
/// behavior change at startup.
Future<void> _initBackgroundGeofencingIfEnabled() async {
  final prefs = await SharedPreferences.getInstance();
  if (prefs.getBool('station_geofencing_enabled') ?? false) {
    await StationGeofenceService().initializeAndSync();
  }
}

class CommuteOSApp extends StatelessWidget {
  const CommuteOSApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CommuteOS',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: const RootShell(),
    );
  }
}
