import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:shared_preferences/shared_preferences.dart';

class EncryptionService {
  static const String _keyAlias = 'gift_monitor_key';
  static const String _saltKey = 'encryption_salt';
  
  /// Генерация случайного ключа
  static String _generateKey() {
    final random = Random.secure();
    final values = List<int>.generate(32, (i) => random.nextInt(256));
    return base64Url.encode(values);
  }
  
  /// Получить или создать ключ шифрования
  static Future<String> _getOrCreateKey() async {
    final prefs = await SharedPreferences.getInstance();
    String? key = prefs.getString(_keyAlias);
    
    if (key == null) {
      key = _generateKey();
      await prefs.setString(_keyAlias, key);
    }
    
    return key;
  }
  
  /// Получить или создать соль
  static Future<String> _getOrCreateSalt() async {
    final prefs = await SharedPreferences.getInstance();
    String? salt = prefs.getString(_saltKey);
    
    if (salt == null) {
      final random = Random.secure();
      final values = List<int>.generate(16, (i) => random.nextInt(256));
      salt = base64Url.encode(values);
      await prefs.setString(_saltKey, salt);
    }
    
    return salt;
  }
  
  /// Зашифровать строку
  static Future<String> encrypt(String plainText) async {
    try {
      final key = await _getOrCreateKey();
      final salt = await _getOrCreateSalt();
      
      // Создаем ключ из пароля и соли
      final keyBytes = utf8.encode(key);
      final saltBytes = utf8.encode(salt);
      final hmac = Hmac(sha256, saltBytes);
      final digest = hmac.convert(keyBytes);
      
      // Простое XOR шифрование (для production используйте AES)
      final plainBytes = utf8.encode(plainText);
      final keyStream = digest.bytes;
      final encrypted = List<int>.generate(plainBytes.length, (i) {
        return plainBytes[i] ^ keyStream[i % keyStream.length];
      });
      
      return base64Url.encode(encrypted);
    } catch (e) {
      print('[EncryptionService] Ошибка шифрования: $e');
      return plainText; // В случае ошибки возвращаем исходный текст
    }
  }
  
  /// Расшифровать строку
  static Future<String> decrypt(String encryptedText) async {
    try {
      final key = await _getOrCreateKey();
      final salt = await _getOrCreateSalt();
      
      // Создаем ключ из пароля и соли
      final keyBytes = utf8.encode(key);
      final saltBytes = utf8.encode(salt);
      final hmac = Hmac(sha256, saltBytes);
      final digest = hmac.convert(keyBytes);
      
      // Расшифровываем
      final encrypted = base64Url.decode(encryptedText);
      final keyStream = digest.bytes;
      final decrypted = List<int>.generate(encrypted.length, (i) {
        return encrypted[i] ^ keyStream[i % keyStream.length];
      });
      
      return utf8.decode(decrypted);
    } catch (e) {
      print('[EncryptionService] Ошибка расшифровки: $e');
      return encryptedText; // В случае ошибки возвращаем исходный текст
    }
  }
  
  /// Зашифровать Map (например, настройки)
  static Future<String> encryptMap(Map<String, dynamic> data) async {
    final jsonString = json.encode(data);
    return await encrypt(jsonString);
  }
  
  /// Расшифровать Map
  static Future<Map<String, dynamic>> decryptMap(String encryptedData) async {
    try {
      final jsonString = await decrypt(encryptedData);
      return json.decode(jsonString);
    } catch (e) {
      print('[EncryptionService] Ошибка расшифровки Map: $e');
      return {};
    }
  }
  
  /// Хэшировать пароль или другие данные
  static String hash(String data) {
    final bytes = utf8.encode(data);
    final digest = sha256.convert(bytes);
    return digest.toString();
  }
  
  /// Проверить целостность данных
  static bool verifyIntegrity(String data, String hash) {
    return hash == EncryptionService.hash(data);
  }
}