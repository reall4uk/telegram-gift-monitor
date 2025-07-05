import 'dart:async';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_background_service_android/flutter_background_service_android.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';
import 'notification_service.dart';
import '../models/gift.dart';

/// Фоновый сервис для мониторинга подарков
@pragma('vm:entry-point')
class BackgroundService {
  static const String _notificationChannelId = 'gift_monitor_foreground';
  static const int _serviceId = 888;
  
  /// Инициализация фонового сервиса
  static Future<bool> initialize() async {
    final service = FlutterBackgroundService();
    
    return await service.configure(
      androidConfiguration: AndroidConfiguration(
        onStart: onStart,
        autoStart: false,
        isForegroundMode: true,
        notificationChannelId: _notificationChannelId,
        initialNotificationTitle: 'Gift Monitor',
        initialNotificationContent: 'Мониторинг подарков активен',
        foregroundServiceNotificationId: _serviceId,
      ),
      iosConfiguration: IosConfiguration(
        autoStart: false,
        onForeground: onStart,
        onBackground: onIosBackground,
      ),
    );
  }
  
  /// Запуск фонового мониторинга
  static Future<void> startBackgroundMonitoring() async {
    final service = FlutterBackgroundService();
    final isRunning = await service.isRunning();
    
    print('[BackgroundService] Попытка запуска. Уже работает: $isRunning');
    
    if (!isRunning) {
      final success = await service.startService();
      print('[BackgroundService] Результат запуска: $success');
      if (success) {
        print('[BackgroundService] Фоновый мониторинг успешно запущен');
      } else {
        print('[BackgroundService] ОШИБКА: Не удалось запустить сервис');
      }
    } else {
      print('[BackgroundService] Сервис уже работает');
    }
  }
  
  /// Остановка фонового мониторинга
  static Future<void> stopBackgroundMonitoring() async {
    final service = FlutterBackgroundService();
    service.invoke('stopService');
    print('[BackgroundService] Фоновый мониторинг остановлен');
  }
  
  /// Проверка статуса
  static Future<bool> isBackgroundServiceRunning() async {
    final service = FlutterBackgroundService();
    return await service.isRunning();
  }
  
  /// Точка входа для фонового сервиса
  @pragma('vm:entry-point')
  static void onStart(ServiceInstance service) async {
    // Для Android показываем foreground уведомление
    if (service is AndroidServiceInstance) {
      service.on('stopService').listen((event) {
        service.stopSelf();
      });
      
      // Запускаем как foreground сервис
      service.setAsForegroundService();
      
      // Обновляем уведомление
      service.setForegroundNotificationInfo(
        title: "Gift Monitor",
        content: "Мониторинг подарков активен",
      );
    }
    
    // Инициализируем сервисы
    final apiService = ApiService();
    final notificationService = NotificationService();
    await notificationService.initialize();
    
    // Загружаем виденные подарки
    final prefs = await SharedPreferences.getInstance();
    var seenIds = prefs.getStringList('seen_gift_ids') ?? [];
    var seenGiftIds = seenIds.toSet();
    
    print('[BackgroundService] Сервис запущен, виденных подарков: ${seenGiftIds.length}');
    
    // Таймер для периодической проверки
    Timer.periodic(const Duration(seconds: 30), (timer) async {
      print('[BackgroundService] Проверка новых подарков...');
      
      try {
        // Проверяем настройки
        final prefs = await SharedPreferences.getInstance();
        final backgroundEnabled = prefs.getBool('background_enabled') ?? false;
        final notificationsEnabled = prefs.getBool('notifications_enabled') ?? false;
        
        if (!backgroundEnabled || !notificationsEnabled) {
          print('[BackgroundService] Мониторинг отключен в настройках');
          return;
        }
        
        // Получаем настройки фильтров
        final minPrice = prefs.getDouble('min_price') ?? 0;
        final soundType = prefs.getString('notification_sound') ?? 'default';
        final volume = prefs.getDouble('notification_volume') ?? 1.0;
        
        // Получаем последние подарки
        List<Gift> gifts;
        try {
          gifts = await apiService.getRecentGifts();
        } catch (e) {
          print('[BackgroundService] Ошибка API: $e');
          return;
        }
        
        print('[BackgroundService] Получено ${gifts.length} подарков');
        
        int newGiftsCount = 0;
        final newSeenIds = <String>[];
        
        // Проверяем каждый подарок
        for (var gift in gifts) {
          if (!seenGiftIds.contains(gift.id)) {
            // Применяем фильтр по цене
            final priceString = gift.price.replaceAll(',', '').replaceAll(' ', '');
            final price = double.tryParse(priceString) ?? 0;
            if (price < minPrice) {
              print('[BackgroundService] Подарок ${gift.id} пропущен: цена $price < $minPrice');
              continue;
            }
            
            // Новый подарок!
            newSeenIds.add(gift.id);
            newGiftsCount++;
            
            // Показываем уведомление
            await notificationService.showGiftNotification(
              giftId: gift.id,
              price: gift.price,
              title: gift.name ?? 'Новый подарок!',
              isLimited: gift.isLimited,
              soundType: soundType,
              volume: volume,
            );
            
            print('[BackgroundService] НОВЫЙ ПОДАРОК: ${gift.name} - ${gift.price} ⭐');
            
            // Задержка между уведомлениями
            if (newGiftsCount > 1) {
              await Future.delayed(const Duration(seconds: 2));
            }
          }
        }
        
        // Сохраняем новые виденные подарки
        if (newSeenIds.isNotEmpty) {
          seenGiftIds.addAll(newSeenIds);
          await prefs.setStringList('seen_gift_ids', seenGiftIds.toList());
          print('[BackgroundService] Найдено $newGiftsCount новых подарков!');
          
          // Обновляем уведомление сервиса
          if (service is AndroidServiceInstance) {
            service.setForegroundNotificationInfo(
              title: "Gift Monitor",
              content: "Найдено новых подарков: $newGiftsCount",
            );
          }
        } else {
          print('[BackgroundService] Новых подарков не найдено');
        }
        
        // Обновляем данные сервиса
        service.invoke(
          'update',
          {
            "current_date": DateTime.now().toIso8601String(),
            "gift_count": gifts.length,
            "new_gifts": newGiftsCount,
          },
        );
        
      } catch (e) {
        print('[BackgroundService] Ошибка: $e');
      }
    });
  }
  
  /// Для iOS (ограниченная поддержка)
  @pragma('vm:entry-point')
  static Future<bool> onIosBackground(ServiceInstance service) async {
    return true;
  }
  
  /// Сброс виденных подарков (для тестирования)
  static Future<void> resetSeenGifts() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('seen_gift_ids');
    print('[BackgroundService] Виденные подарки сброшены');
  }
}