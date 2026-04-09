package com.sachinmeier.jdivoiceandroid.service

import android.Manifest
import android.content.pm.PackageManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.content.ContextCompat
import com.sachinmeier.jdivoiceandroid.JdiVoiceApplication
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class VoiceForegroundService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private lateinit var notificationHelper: NotificationHelper
    private lateinit var engine: VoiceEngine

    override fun onCreate() {
        super.onCreate()
        val appContainer = (application as JdiVoiceApplication).appContainer
        notificationHelper = NotificationHelper(this)
        notificationHelper.createChannel()
        engine = VoiceEngine(appContainer)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action ?: ACTION_START_SERVICE) {
            ACTION_START_SERVICE -> startVoiceService()
            ACTION_STOP_SERVICE -> stopVoiceService()
            ACTION_MANUAL_PRESS -> engine.onManualPress()
            ACTION_MANUAL_RELEASE -> engine.onManualRelease()
            ACTION_RELOAD_CONFIG -> runSafely { engine.reload() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        runSafely { engine.stop() }
        super.onDestroy()
    }

    private fun startVoiceService() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            VoiceRuntimeStore.update {
                it.copy(errorMessage = "Microphone permission is required before starting the voice service.")
            }
            stopSelf()
            return
        }
        startForeground(
            NotificationHelper.NOTIFICATION_ID,
            notificationHelper.buildNotification("Voice service running"),
        )
        runSafely { engine.start() }
    }

    private fun stopVoiceService() {
        serviceScope.launch {
            try {
                engine.stop()
            } catch (error: Throwable) {
                VoiceRuntimeStore.update {
                    it.copy(errorMessage = error.message ?: "Unexpected service error.")
                }
            }
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private fun runSafely(block: suspend () -> Unit) {
        serviceScope.launch {
            try {
                block()
            } catch (error: Throwable) {
                VoiceRuntimeStore.update {
                    it.copy(errorMessage = error.message ?: "Unexpected service error.")
                }
            }
        }
    }

    companion object {
        const val ACTION_START_SERVICE = "com.sachinmeier.jdivoiceandroid.action.START"
        const val ACTION_STOP_SERVICE = "com.sachinmeier.jdivoiceandroid.action.STOP"
        const val ACTION_MANUAL_PRESS = "com.sachinmeier.jdivoiceandroid.action.MANUAL_PRESS"
        const val ACTION_MANUAL_RELEASE = "com.sachinmeier.jdivoiceandroid.action.MANUAL_RELEASE"
        const val ACTION_RELOAD_CONFIG = "com.sachinmeier.jdivoiceandroid.action.RELOAD"

        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, VoiceForegroundService::class.java).setAction(ACTION_START_SERVICE),
            )
        }

        fun stop(context: Context) {
            context.startService(
                Intent(context, VoiceForegroundService::class.java).setAction(ACTION_STOP_SERVICE),
            )
        }

        fun manualPress(context: Context) {
            context.startService(
                Intent(context, VoiceForegroundService::class.java).setAction(ACTION_MANUAL_PRESS),
            )
        }

        fun manualRelease(context: Context) {
            context.startService(
                Intent(context, VoiceForegroundService::class.java).setAction(ACTION_MANUAL_RELEASE),
            )
        }

        fun reloadConfig(context: Context) {
            context.startService(
                Intent(context, VoiceForegroundService::class.java).setAction(ACTION_RELOAD_CONFIG),
            )
        }
    }
}
