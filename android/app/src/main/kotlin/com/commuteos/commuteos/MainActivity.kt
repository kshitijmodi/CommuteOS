package com.commuteos.commuteos

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var activityTransitionPlugin: ActivityTransitionPlugin? = null

    companion object {
        /** Set while this Activity is alive - lets ActivityTransitionReceiver
         * (a separate BroadcastReceiver, not part of this Activity's
         * lifecycle) forward a real transition event to Dart via the plugin
         * instance's event sink. Null (and the event silently dropped) if
         * the Activity isn't currently running - acceptable since this
         * feature is deliberately foreground-only for now, see
         * ActivityTransitionPlugin's class doc.
         */
        var activePlugin: ActivityTransitionPlugin? = null
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        val plugin = ActivityTransitionPlugin(this)
        activityTransitionPlugin = plugin
        activePlugin = plugin

        val methodChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "commuteos/activity_transition",
        )
        val eventChannel = EventChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "commuteos/activity_transition_events",
        )
        plugin.bind(methodChannel, eventChannel)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        val handled = activityTransitionPlugin?.onRequestPermissionsResult(requestCode, grantResults) ?: false
        if (!handled) {
            super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        }
    }

    override fun onDestroy() {
        if (activePlugin === activityTransitionPlugin) {
            activePlugin = null
        }
        super.onDestroy()
    }
}
