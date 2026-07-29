import 'package:flutter/material.dart';

import 'mta/arrivals_screen.dart';
import 'mta/mta_feed.dart';

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
      home: const ArrivalsScreen(
        title: 'Union Square (N/Q/R/W, northbound)',
        feed: MtaFeed.nqrw,
        stopId: 'R16N',
      ),
    );
  }
}
