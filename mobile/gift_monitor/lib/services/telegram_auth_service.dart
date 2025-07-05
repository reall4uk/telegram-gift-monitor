import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'config_service.dart';
import 'security_service.dart';
import 'encryption_service.dart';

class TelegramAuthService {
  // Получаем токен из ConfigService (безопасно)
  static Future<String> get botToken async {
    final token = await ConfigService.getBotToken();
    if (token == null || token.isEmpty) {
      throw Exception('Не удалось получить токен бота');
    }
    return token;
  }
  
  // Получаем канал из конфигурации
  static Future<String> get requiredChannel async {
    return await ConfigService.getRequiredChannel();
  }
  
  // Каналы для мониторинга теперь берем с сервера
  static Future<List<String>> get monitoringChannels async {
    return await ConfigService.getMonitoringChannels();
  }
  
  /// Проверка подписки на канал авторизации
  static Future<bool> checkSubscription(String userId) async {
    try {
      final token = await botToken;
      final channel = await requiredChannel;
      
      print('[Auth] Проверка подписки для пользователя: $userId');
      print('[Auth] Канал для проверки: $channel');
      print('[Auth] Токен бота: ${token.isNotEmpty ? "загружен" : "ОТСУТСТВУЕТ"}');
      
      // Проверяем, что токен загружен
      if (token.isEmpty) {
        print('[Auth] ОШИБКА: токен бота не найден!');
        return false;
      }
      
      final url = 'https://api.telegram.org/bot$token/getChatMember'
          '?chat_id=$channel&user_id=$userId';
      
      print('[Auth] Отправляем запрос к Telegram API...');
      final response = await http.get(Uri.parse(url));
      
      print('[Auth] Ответ получен: ${response.statusCode}');
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        print('[Auth] Данные: ${data['result']}');
        
        final status = data['result']['status'];
        print('[Auth] Статус пользователя в канале: $status');
        
        // Пользователь должен быть member, administrator или creator
        if (status == 'left' || status == 'kicked') {
          print('[Auth] Пользователь НЕ подписан на $channel');
          return false;
        }
        print('[Auth] Пользователь ПОДПИСАН на канал');
        return true;
      } else {
        print('[Auth] Ошибка проверки канала: ${response.body}');
        return false;
      }
    } catch (e) {
      print('[Auth] ОШИБКА проверки подписки: $e');
      return false;
    }
  }
  
  /// Сохранение авторизации (только User ID)
  static Future<void> saveAuth(String userId) async {
    final prefs = await SharedPreferences.getInstance();
    // Шифруем User ID перед сохранением
    final encryptedUserId = await EncryptionService.encrypt(userId);
    await prefs.setString('telegram_user_id', encryptedUserId);
    await prefs.setBool('is_authorized', true);
    print('[Auth] Авторизация сохранена для пользователя');
  }
  
  /// Получить сохраненный User ID
  static Future<String?> getSavedUserId() async {
    final prefs = await SharedPreferences.getInstance();
    final encryptedUserId = prefs.getString('telegram_user_id');
    if (encryptedUserId != null) {
      return await EncryptionService.decrypt(encryptedUserId);
    }
    return null;
  }
  
  /// Проверка авторизации
  static Future<bool> isAuthorized() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('is_authorized') ?? false;
  }
  
  /// Выход
  static Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    print('[Auth] Пользователь вышел из системы');
  }
}