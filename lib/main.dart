import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

import 'design/root_shell.dart';
import 'design/theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Android-only target: no explicit FirebaseOptions needed - the
  // google-services.json-driven Gradle plugin supplies them. See
  // push_registration_service.dart for what this app actually uses
  // Firebase for (just FCM tokens/push, nothing else).
  await Firebase.initializeApp();
  runApp(const CommuteOSApp());
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
