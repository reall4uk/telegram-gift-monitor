import 'dart:io';
import 'package:flutter/services.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'encryption_service.dart';

class SecurityService {
  static const platform = MethodChannel('gift_monitor_security');
  
  // Ожидаемая подпись приложения (SHA-256)
  static const String _expectedSignature = 'YOUR_APP_SIGNATURE_HERE';
  
  /// Проверить целостность приложения
  static Future<bool> verifyAppIntegrity() async {
    try {
      // Проверяем debug режим
      if (const bool.fromEnvironment('dart.vm.product') == false) {
        print('[SecurityService] Debug режим, пропускаем проверку');
        return true;
      }
      
      // Проверяем подпись APK (только Android)
      if (Platform.isAndroid) {
        final isValid = await _verifyApkSignature();
        if (!isValid) {
          print('[SecurityService] Неверная подпись APK!');
          return false;
        }
      }
      
      // Проверяем root/jailbreak
      final isCompromised = await _checkDeviceCompromised();
      if (isCompromised) {
        print('[SecurityService] Устройство скомпрометировано (root/jailbreak)');
        return false;
      }
      
      // Проверяем отладчик
      final hasDebugger = await _checkDebugger();
      if (hasDebugger) {
        print('[SecurityService] Обнаружен отладчик');
        return false;
      }
      
      return true;
    } catch (e) {
      print('[SecurityService] Ошибка проверки безопасности: $e');
      return false;
    }
  }
  
  /// Проверить подпись APK
  static Future<bool> _verifyApkSignature() async {
    try {
      final String signature = await platform.invokeMethod('getApkSignature');
      return signature == _expectedSignature;
    } catch (e) {
      print('[SecurityService] Ошибка проверки подписи: $e');
      return false;
    }
  }
  
  /// Проверить root/jailbreak
  static Future<bool> _checkDeviceCompromised() async {
    if (Platform.isAndroid) {
      // Проверяем наличие файлов root
      final rootFiles = [
        '/system/app/Superuser.apk',
        '/sbin/su',
        '/system/bin/su',
        '/system/xbin/su',
        '/data/local/xbin/su',
        '/data/local/bin/su',
        '/system/sd/xbin/su',
        '/system/bin/failsafe/su',
        '/data/local/su',
      ];
      
      for (final path in rootFiles) {
        if (File(path).existsSync()) {
          return true;
        }
      }
      
      // Проверяем build tags
      try {
        final buildTags = await platform.invokeMethod('getBuildTags');
        if (buildTags.contains('test-keys')) {
          return true;
        }
      } catch (e) {
        // Игнорируем ошибку
      }
    }
    
    return false;
  }
  
  /// Проверить наличие отладчика
  static Future<bool> _checkDebugger() async {
    try {
      final isDebuggerAttached = await platform.invokeMethod('isDebuggerAttached');
      return isDebuggerAttached;
    } catch (e) {
      return false;
    }
  }
  
  /// Обфусцировать строку (простая защита)
  static String obfuscate(String input) {
    return input.split('').reversed.join('');
  }
  
  /// Деобфусцировать строку
  static String deobfuscate(String input) {
    return input.split('').reversed.join('');
  }
  
  /// Получить информацию о приложении
  static Future<Map<String, String>> getAppInfo() async {
    final packageInfo = await PackageInfo.fromPlatform();
    return {
      'appName': packageInfo.appName,
      'packageName': packageInfo.packageName,
      'version': packageInfo.version,
      'buildNumber': packageInfo.buildNumber,
    };
  }
  
  /// Безопасное хранение критичных данных
  static Future<void> secureStore(String key, String value) async {
    // В production используйте flutter_secure_storage
    final encrypted = await EncryptionService.encrypt(value);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('secure_$key', encrypted);
  }
  
  /// Безопасное получение данных
  static Future<String?> secureGet(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final encrypted = prefs.getString('secure_$key');
    if (encrypted != null) {
      return await EncryptionService.decrypt(encrypted);
    }
    return null;
  }
}