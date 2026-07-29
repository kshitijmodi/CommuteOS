import 'package:flutter/material.dart';

import 'mta/station_search_screen.dart';

void main() {
  runApp(const CommuteOSApp());
}

class CommuteOSApp extends StatelessWidget {
  const CommuteOSApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CommuteOS',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal)),
      home: const StationSearchScreen(),
    );
  }
}
