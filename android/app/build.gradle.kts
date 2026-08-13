plugins {
    id("com.android.application")
    // Reads android/app/google-services.json to configure Firebase (see
    // lib/account/push_registration_service.dart).
    id("com.google.gms.google-services")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.commuteos.commuteos"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // Kept enabled even though flutter_local_notifications (which
        // originally needed this) was removed - Firebase Cloud Messaging,
        // the real push mechanism this is moving toward (see
        // push_registration_service.dart), commonly needs it too.
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.commuteos.commuteos"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
            // Real crash fixed 2026-08-13, 100% reproducible on every cold
            // start of a release build - see proguard-rules.pro's own
            // comment for the full root cause (R8 stripping WorkManager's
            // Room-generated WorkDatabase_Impl with no keep rule for it,
            // a real gap only exposed once native_geofence made
            // WorkManager a load-bearing runtime dependency). This
            // explicit isMinifyEnabled=true (matching the Flutter Gradle
            // Plugin's own release default, now made visible rather than
            // implicit) plus the proguard rules file is the actual fix -
            // not disabling minification, which would just hide the next
            // R8-stripped-reflection bug instead of protecting against it.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
    // ActivityRecognitionClient/ActivityTransitionRequest - see
    // ActivityTransitionPlugin.kt (Behavior AI's passive timing-buffer
    // signal, still -> walking/in_vehicle detection).
    implementation("com.google.android.gms:play-services-location:21.4.0")
}
