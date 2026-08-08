package com.commuteos.commuteos

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.gms.location.ActivityRecognition
import com.google.android.gms.location.ActivityTransition
import com.google.android.gms.location.ActivityTransitionRequest
import com.google.android.gms.location.ActivityTransitionResult
import com.google.android.gms.location.DetectedActivity
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

private const val METHOD_CHANNEL = "commuteos/activity_transition"
private const val EVENT_CHANNEL = "commuteos/activity_transition_events"
private const val ACTIVITY_RECOGNITION_REQUEST_CODE = 9001
private const val ACTION_ACTIVITY_TRANSITION = "com.commuteos.commuteos.ACTION_ACTIVITY_TRANSITION"

/**
 * Bridges Google Play Services' Activity Recognition Transition API to
 * Dart - powers Behavior AI's passive timing-buffer signal (see
 * lib/behavior/departure_detector.dart): detecting a still->walking or
 * still->in_vehicle transition, timestamped Dart-side as a candidate
 * "the user started moving" moment, no GPS/location permission involved.
 *
 * Deliberately foreground-only for this first version (see
 * OPEN_QUESTIONS.md) - registered from MainActivity.onResume/onPause
 * rather than a background service, since every current Flutter plugin
 * wrapping this API has documented background-reliability gaps
 * (screen-off, OEM battery managers, long-uptime stream death) that a
 * small foreground-only scope avoids entirely rather than papering over.
 *
 * Only STILL->WALKING and STILL->IN_VEHICLE (ENTER) transitions are
 * requested - this app only needs "did the user start moving," not a
 * full activity classification.
 */
class ActivityTransitionPlugin(private val activity: Activity) :
    MethodChannel.MethodCallHandler, EventChannel.StreamHandler {

    private val client = ActivityRecognition.getClient(activity)
    private var eventSink: EventChannel.EventSink? = null
    private var pendingPermissionResult: MethodChannel.Result? = null

    private val pendingIntent: PendingIntent by lazy {
        val intent = Intent(ACTION_ACTIVITY_TRANSITION).apply {
            setPackage(activity.packageName)
        }
        PendingIntent.getBroadcast(
            activity,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
        )
    }

    fun bind(methodChannel: MethodChannel, eventChannel: EventChannel) {
        methodChannel.setMethodCallHandler(this)
        eventChannel.setStreamHandler(this)
    }

    override fun onMethodCall(call: io.flutter.plugin.common.MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "hasPermission" -> result.success(hasActivityRecognitionPermission())
            "requestPermission" -> requestPermission(result)
            "start" -> start(result)
            "stop" -> stop(result)
            else -> result.notImplemented()
        }
    }

    private fun hasActivityRecognitionPermission(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return true
        return ContextCompat.checkSelfPermission(
            activity,
            Manifest.permission.ACTIVITY_RECOGNITION,
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestPermission(result: MethodChannel.Result) {
        if (hasActivityRecognitionPermission()) {
            result.success(true)
            return
        }
        pendingPermissionResult = result
        ActivityCompat.requestPermissions(
            activity,
            arrayOf(Manifest.permission.ACTIVITY_RECOGNITION),
            ACTIVITY_RECOGNITION_REQUEST_CODE,
        )
    }

    /** Called from MainActivity.onRequestPermissionsResult. */
    fun onRequestPermissionsResult(requestCode: Int, grantResults: IntArray): Boolean {
        if (requestCode != ACTIVITY_RECOGNITION_REQUEST_CODE) return false
        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        pendingPermissionResult?.success(granted)
        pendingPermissionResult = null
        return true
    }

    private fun start(result: MethodChannel.Result) {
        if (!hasActivityRecognitionPermission()) {
            result.error("NO_PERMISSION", "ACTIVITY_RECOGNITION not granted", null)
            return
        }

        val transitions = listOf(
            ActivityTransition.Builder()
                .setActivityType(DetectedActivity.WALKING)
                .setActivityTransition(ActivityTransition.ACTIVITY_TRANSITION_ENTER)
                .build(),
            ActivityTransition.Builder()
                .setActivityType(DetectedActivity.IN_VEHICLE)
                .setActivityTransition(ActivityTransition.ACTIVITY_TRANSITION_ENTER)
                .build(),
        )
        val request = ActivityTransitionRequest(transitions)

        client.requestActivityTransitionUpdates(request, pendingIntent)
            .addOnSuccessListener { result.success(true) }
            .addOnFailureListener { e -> result.error("START_FAILED", e.message, null) }
    }

    private fun stop(result: MethodChannel.Result) {
        client.removeActivityTransitionUpdates(pendingIntent)
            .addOnSuccessListener { result.success(true) }
            .addOnFailureListener { e -> result.error("STOP_FAILED", e.message, null) }
    }

    override fun onListen(arguments: Any?, sink: EventChannel.EventSink) {
        eventSink = sink
    }

    override fun onCancel(arguments: Any?) {
        eventSink = null
    }

    /** Called by ActivityTransitionReceiver when a real transition event
     * arrives - forwards it to Dart as a plain string ("walking" /
     * "in_vehicle") over the event channel. The exact elapsed-time field
     * on ActivityTransitionEvent isn't used here - Dart stamps its own
     * DateTime.now() on receipt, which is precise enough for a timing
     * -buffer signal measured in minutes, and avoids depending on a
     * Play Services field whose exact name varies across versions/docs.
     */
    fun onTransitionEvent(activityType: Int) {
        val label = when (activityType) {
            DetectedActivity.WALKING -> "walking"
            DetectedActivity.IN_VEHICLE -> "in_vehicle"
            else -> return
        }
        eventSink?.success(label)
    }
}

/** Registered in AndroidManifest.xml, exported="false" - only ever
 * triggered via the explicit PendingIntent above, never a guessable
 * broadcast action from another app.
 */
class ActivityTransitionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (!ActivityTransitionResult.hasResult(intent)) return
        val result = ActivityTransitionResult.extractResult(intent) ?: return
        val plugin = MainActivity.activePlugin ?: return
        for (event in result.transitionEvents) {
            plugin.onTransitionEvent(event.activityType)
        }
    }
}
