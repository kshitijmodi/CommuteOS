# Real crash fixed 2026-08-13: a release build (minifyEnabled defaults to
# true via the Flutter Gradle Plugin's release template, even though this
# file previously didn't exist to configure it) crashed on EVERY launch -
# java.lang.RuntimeException: Unable to get provider
# androidx.startup.InitializationProvider, caused by
# java.lang.NoSuchMethodException: androidx.work.impl.WorkDatabase_Impl.<init>
#
# Root cause: WorkManager (a real, load-bearing dependency once
# native_geofence was added this session - see
# lib/behavior/station_geofence_service.dart's docs) uses Room, and Room
# generates a WorkDatabase_Impl class at compile time that's instantiated
# via reflection at runtime, not a direct constructor call R8 can see.
# With no keep rules for it, R8's default aggressive stripping renamed/
# removed the no-arg constructor reflection needs, so WorkManagerInitializer
# (itself started automatically by AndroidX Startup's InitializationProvider,
# which is why the crash surfaces as "can't get that provider" rather than
# naming WorkManager directly) failed immediately on every cold start -
# not an occasional bug, a 100% reproducible launch crash once minification
# ran. native_geofence ships no consumer ProGuard rules of its own for
# this, so the app needs its own.
-keep class androidx.work.impl.WorkDatabase_Impl { <init>(); }
-keep class androidx.work.impl.** { *; }
-keep class * extends androidx.room.RoomDatabase { <init>(); }
-dontwarn androidx.work.**
