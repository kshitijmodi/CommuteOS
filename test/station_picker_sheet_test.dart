import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:commuteos/design/components.dart';
import 'package:commuteos/mta/mta_station.dart';
import 'package:commuteos/njt/njt_bus_stop.dart';
import 'package:commuteos/njt/njt_rail_station.dart';
import 'package:commuteos/path/path_station.dart';
import 'package:commuteos/transit/station_group.dart';
import 'package:commuteos/transit/station_picker_sheet.dart';
import 'package:commuteos/transit/transit_models.dart';

const _path = PathStation(code: 'JSQ', name: 'Journal Square', state: 'NJ');
const _njtRail = NjtRailStation(code: 'JSQ', name: 'Journal Square', lines: ['NEC']);
const _njtBus1 = NjtBusStop(stopId: '1', name: 'Journal Square', routeNames: ['1']);
const _njtBus2 = NjtBusStop(stopId: '2', name: 'Journal Square', routeNames: ['2']);

Future<TransitStation?> _showPicker(WidgetTester tester, StationGroup group) async {
  TransitStation? result;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => ElevatedButton(
            onPressed: () async {
              result = await showStationPicker(context, group);
            },
            child: const Text('Open'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();
  return result;
}

void main() {
  testWidgets('shows no agency filter chips for a single-agency collision', (tester) async {
    const mta1 = MtaStation(
      gtfsStopId: 'A',
      complexId: '1',
      name: '23 St',
      borough: 'M',
      routes: ['N'],
      northLabel: 'Uptown',
      southLabel: 'Downtown',
    );
    const mta2 = MtaStation(
      gtfsStopId: 'B',
      complexId: '2',
      name: '23 St',
      borough: 'M',
      routes: ['1'],
      northLabel: 'Uptown',
      southLabel: 'Downtown',
    );
    final group = StationGroup(name: '23 St', stations: const [mta1, mta2]);

    await _showPicker(tester, group);

    expect(find.text('All'), findsNothing);
    expect(find.text('PATH'), findsNothing);
  });

  testWidgets('shows agency filter chips for a multi-agency hub', (tester) async {
    final group = StationGroup(
      name: 'Journal Square',
      stations: const [_path, _njtRail, _njtBus1, _njtBus2],
    );

    await _showPicker(tester, group);

    expect(find.widgetWithText(ChoiceChip, 'All'), findsOneWidget);
    expect(find.widgetWithText(ChoiceChip, 'PATH'), findsOneWidget);
    expect(find.widgetWithText(ChoiceChip, 'NJT Rail'), findsOneWidget);
    expect(find.widgetWithText(ChoiceChip, 'NJT Bus'), findsOneWidget);
  });

  testWidgets('filtering to one agency hides other agencies\' rows', (tester) async {
    final group = StationGroup(
      name: 'Journal Square',
      stations: const [_path, _njtRail, _njtBus1, _njtBus2],
    );

    await _showPicker(tester, group);

    // Under "All", both NJT bus route chips (from _njtBus1/_njtBus2) are visible.
    expect(find.text('1'), findsOneWidget);
    expect(find.text('2'), findsOneWidget);

    // Tap the "NJT Bus" filter chip specifically.
    await tester.tap(find.widgetWithText(ChoiceChip, 'NJT Bus'));
    await tester.pumpAndSettle();

    // Bus route chips still there, but the PATH row's RouteChip badge
    // (which also renders the literal text "PATH") is now gone - the
    // filter chip labeled "PATH" is a different widget type, so this
    // specifically checks the row, not the still-visible filter chip.
    expect(find.text('1'), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    expect(find.widgetWithText(RouteChip, 'PATH'), findsNothing);
  });

  testWidgets('tapping a station returns it from the sheet', (tester) async {
    final group = StationGroup(name: 'Journal Square', stations: const [_path, _njtRail]);
    TransitStation? tapped;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () async {
                tapped = await showStationPicker(context, group);
              },
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('NEC'));
    await tester.pumpAndSettle();

    expect(tapped, same(_njtRail));
  });
}
