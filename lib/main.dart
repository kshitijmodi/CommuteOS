import 'package:flutter/material.dart';

import 'design/root_shell.dart';
import 'design/theme.dart';

void main() {
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
