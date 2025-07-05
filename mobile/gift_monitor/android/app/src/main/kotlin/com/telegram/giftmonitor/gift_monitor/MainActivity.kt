package com.telegram.giftmonitor.gift_monitor

import io.flutter.embedding.android.FlutterActivity
import android.os.Bundle
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNotificationChannel()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "gift_monitor_foreground",
                "Фоновый мониторинг",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Постоянное уведомление для работы в фоне"
                setShowBadge(false)
                enableVibration(false)
                setSound(null, null)
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
            
            println("[MainActivity] Notification channel created: gift_monitor_foreground")
        }
    }
}