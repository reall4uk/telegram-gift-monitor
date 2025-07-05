import 'dart:io' show Platform;
import 'dart:typed_data' show Int32List, Int64List;
import 'package:flutter/material.dart' show Color;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notifications = FlutterLocalNotificationsPlugin();
  bool _isInitialized = false;

  /// Инициализация сервиса уведомлений
  Future<void> initialize() async {
    if (_isInitialized) return;

    // Настройки для Android
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    
    // Общие настройки
    const initSettings = InitializationSettings(
      android: androidSettings,
    );

    // Инициализация
    await _notifications.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    // Запрос разрешений
    await _requestPermissions();
    
    // Создаем каналы уведомлений
    await _createNotificationChannels();
    
    _isInitialized = true;
    print('[NotificationService] Инициализация завершена');
  }

  /// Создание каналов уведомлений для Android
  Future<void> _createNotificationChannels() async {
    if (Platform.isAndroid) {
      final androidPlugin = _notifications
          .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
      
      if (androidPlugin != null) {
        // Канал для стандартных уведомлений
        const defaultChannel = AndroidNotificationChannel(
          'gift_standard',
          'Стандартные уведомления',
          description: 'Обычные уведомления о новых подарках',
          importance: Importance.defaultImportance,
          enableVibration: true,
          enableLights: true,
          ledColor: Color(0xFF4ECDC4),
          playSound: true,
        );
        
        // Канал для важных уведомлений (рингтон)
        const ringtoneChannel = AndroidNotificationChannel(
          'gift_ringtone',
          'Важные уведомления',
          description: 'Важные уведомления о редких подарках',
          importance: Importance.high,
          enableVibration: true,
          enableLights: true,
          ledColor: Color(0xFFFFA500),
          playSound: true,
        );
        
        // Канал для срочных уведомлений (будильник)
        const alarmChannel = AndroidNotificationChannel(
          'gift_alarm',
          'Срочные уведомления',
          description: 'Срочные уведомления о лимитированных подарках',
          importance: Importance.max,
          enableVibration: true,
          enableLights: true,
          ledColor: Color(0xFFFF0000),
          playSound: true,
        );
        
        // Канал для фонового сервиса
        const foregroundChannel = AndroidNotificationChannel(
          'gift_monitor_foreground',
          'Фоновый мониторинг',
          description: 'Постоянное уведомление для работы в фоне',
          importance: Importance.low,
          enableVibration: false,
          enableLights: false,
          playSound: false,
          showBadge: false,
        );
        
        // Создаем все каналы
        await androidPlugin.createNotificationChannel(defaultChannel);
        await androidPlugin.createNotificationChannel(ringtoneChannel);
        await androidPlugin.createNotificationChannel(alarmChannel);
        await androidPlugin.createNotificationChannel(foregroundChannel);
        
        print('[NotificationService] Создано 4 канала уведомлений');
      }
    }
  }

  /// Запрос разрешений
  Future<void> _requestPermissions() async {
    if (Platform.isAndroid) {
      // Android 13+ требует разрешение на уведомления
      if (await Permission.notification.isDenied) {
        await Permission.notification.request();
      }
      
      // Разрешение для точных будильников (Android 12+)
      if (await Permission.scheduleExactAlarm.isDenied) {
        await Permission.scheduleExactAlarm.request();
      }
    }
  }

  /// Показать уведомление о новом подарке
  Future<void> showGiftNotification({
    required String giftId,
    required String price, // Изменено на String
    String? title,
    bool isLimited = true,
    String soundType = 'default',
    double volume = 1.0,
  }) async {
    if (!_isInitialized) await initialize();

    try {
      // Загружаем настройки
      final prefs = await SharedPreferences.getInstance();
      final soundEnabled = prefs.getBool('sound_enabled') ?? true;
      final vibrationEnabled = prefs.getBool('vibration_enabled') ?? true;

      // Выбираем звук в зависимости от типа
      AndroidNotificationSound? notificationSound;
      
      if (soundEnabled) {
        switch (soundType) {
          case 'alarm':
            // Для будильника используем максимальную важность
            notificationSound = null; // Системный звук
            break;
          case 'ringtone':
            // Используем системный звук
            notificationSound = null;
            break;
          case 'default':
          default:
            // Использует стандартный звук уведомлений
            notificationSound = null; // null = системный звук по умолчанию
            break;
        }
      }

      // Объявляем локальные переменные для настроек канала
      String channelId;
      String channelName;
      Importance importance;
      Priority priority;
      bool useFullScreenIntent = false;
      
      // Выбираем канал и настройки в зависимости от типа звука
      switch (soundType) {
        case 'alarm':
          channelId = 'gift_alarm';
          channelName = 'Срочные уведомления';
          importance = Importance.max;
          priority = Priority.max;
          useFullScreenIntent = true;
          break;
        case 'ringtone':
          channelId = 'gift_ringtone';
          channelName = 'Важные уведомления';
          importance = Importance.high;
          priority = Priority.high;
          break;
        default:
          channelId = 'gift_standard';
          channelName = 'Стандартные уведомления';
          importance = Importance.defaultImportance;
          priority = Priority.defaultPriority;
          break;
      }

      // Настройки Android уведомления
      final androidDetails = AndroidNotificationDetails(
        channelId,
        channelName,
        channelDescription: 'Уведомления о новых подарках в Telegram',
        importance: importance,
        priority: priority,
        showWhen: true,
        enableVibration: vibrationEnabled,
        vibrationPattern: vibrationEnabled ? Int64List.fromList([0, 500, 200, 500]) : null,
        enableLights: true,
        ledColor: isLimited ? const Color(0xFFFF6B6B) : const Color(0xFF4ECDC4),
        ledOnMs: 1000,
        ledOffMs: 500,
        playSound: soundEnabled,
        sound: notificationSound,
        styleInformation: BigTextStyleInformation(
          'Цена: $price ⭐️\n${isLimited ? "⚡ ЛИМИТИРОВАННЫЙ ПОДАРОК!" : "Новый подарок доступен"}',
          contentTitle: title ?? 'Новый подарок в Telegram!',
          summaryText: isLimited ? '🔥 Редкий' : '🎁 Обычный',
        ),
        ticker: 'Новый подарок: $price ⭐️',
        category: AndroidNotificationCategory.alarm,
        fullScreenIntent: useFullScreenIntent,
        autoCancel: true,
        color: const Color(0xFF4ECDC4),
        icon: '@mipmap/ic_launcher',
        largeIcon: const DrawableResourceAndroidBitmap('@mipmap/ic_launcher'),
        actions: [
          const AndroidNotificationAction(
            'open_gift',
            'Открыть',
            cancelNotification: true,
            showsUserInterface: true,
          ),
        ],
      );

      final details = NotificationDetails(android: androidDetails);

      // Показываем уведомление
      await _notifications.show(
        giftId.hashCode,
        title ?? 'Новый подарок в Telegram!',
        'Цена: $price ⭐️ • ${isLimited ? "Лимитированный!" : "Доступен"}',
        details,
        payload: giftId,
      );

      print('[NotificationService] Уведомление показано: $giftId, звук: $soundType');
    } catch (e) {
      print('[NotificationService] Ошибка показа уведомления: $e');
    }
  }

  /// Показать тестовое уведомление
  Future<void> showTestNotification({
    String soundType = 'default',
    double volume = 1.0,
  }) async {
    await showGiftNotification(
      giftId: 'test_${DateTime.now().millisecondsSinceEpoch}',
      price: '9999',
      title: '🎉 Тестовое уведомление',
      isLimited: true,
      soundType: soundType,
      volume: volume,
    );
  }

  /// Обработка нажатия на уведомление
  void _onNotificationTapped(NotificationResponse response) {
    print('[NotificationService] Уведомление нажато: ${response.payload}');
    // Здесь можно добавить навигацию к конкретному подарку
  }

  /// Отмена всех уведомлений
  Future<void> cancelAll() async {
    await _notifications.cancelAll();
  }

  /// Отмена конкретного уведомления
  Future<void> cancel(int id) async {
    await _notifications.cancel(id);
  }

  /// Запрос разрешения на уведомления
  Future<bool> requestPermission() async {
    if (Platform.isAndroid) {
      final status = await Permission.notification.request();
      return status.isGranted;
    }
    return true;
  }

  /// Отключение уведомлений
  Future<void> disableNotifications() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('notifications_enabled', false);
    await cancelAll();
  }

  /// Сохранение настроек уведомлений
  Future<void> saveNotificationSettings({
    required bool soundEnabled,
    required bool vibrationEnabled,
    required String soundType,
    required double volume,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('sound_enabled', soundEnabled);
    await prefs.setBool('vibration_enabled', vibrationEnabled);
    await prefs.setString('notification_sound', soundType);
    await prefs.setDouble('notification_volume', volume);
    
    print('[NotificationService] Настройки сохранены: звук=$soundType, громкость=$volume');
  }
}