import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

/// Schedules a daily local notification around the user's usual departure
/// time, once home/office inference has a real answer - the proactive
/// nudge the PRD's vision describes, without needing a hosted backend +
/// Firebase Cloud Messaging (see OPEN_QUESTIONS.md for that tradeoff).
///
/// Local-only: this can't be dynamically triggered by the backend (e.g.
/// "only notify if there's a real delay today") - it fires at a fixed
/// time regardless of live conditions. Tapping it opens the app to the
/// recommendation flow, which is where live conditions actually get
/// checked. Upgrading to real server-triggered push is future work once
/// there's a hosting story.
class CommuteNotificationService {
  CommuteNotificationService() : _plugin = FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;

  static const _channelId = 'commute_reminders';
  static const _channelName = 'Commute reminders';
  static const _notificationId = 1;

  Future<void> initialize() async {
    tz_data.initializeTimeZones();

    const androidSettings = AndroidInitializationSettings(
      '@mipmap/ic_launcher',
    );
    const settings = InitializationSettings(android: androidSettings);
    await _plugin.initialize(settings);

    const channel = AndroidNotificationChannel(
      _channelId,
      _channelName,
      description: 'Daily reminder to check your commute',
      importance: Importance.high,
    );
    await _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.createNotificationChannel(channel);
  }

  Future<bool> requestPermission() async {
    final granted = await _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.requestNotificationsPermission();
    return granted ?? false;
  }

  /// Schedules (or reschedules) a daily reminder at [hour]:[minute] local
  /// time. Safe to call repeatedly - each call replaces the prior schedule
  /// for the same notification ID rather than stacking duplicates.
  Future<void> scheduleDailyReminder({
    required int hour,
    required int minute,
    required String title,
    required String body,
  }) async {
    final scheduledDate = _nextInstanceOf(hour, minute);

    await _plugin.zonedSchedule(
      _notificationId,
      title,
      body,
      scheduledDate,
      const NotificationDetails(
        android: AndroidNotificationDetails(_channelId, _channelName),
      ),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time,
    );
  }

  Future<void> cancelDailyReminder() async {
    await _plugin.cancel(_notificationId);
  }

  tz.TZDateTime _nextInstanceOf(int hour, int minute) {
    final now = tz.TZDateTime.now(tz.local);
    var scheduled = tz.TZDateTime(
      tz.local,
      now.year,
      now.month,
      now.day,
      hour,
      minute,
    );
    if (scheduled.isBefore(now)) {
      scheduled = scheduled.add(const Duration(days: 1));
    }
    return scheduled;
  }
}
