import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'encryption_service.dart';
import 'security_service.dart';
import 'package:crypto/crypto.dart';
import 'package:package_info_plus/package_info_plus.dart';

class ConfigService {
  static const String _baseUrl = 'http://localhost:8000'; // Измените на ваш сервер
  static const String _configCacheKey = 'cached_config';
  static const String _configTimestampKey = 'config_timestamp';
  static const String _appTokenKey = 'app_token';
  static const int _cacheValidityMinutes = 30;

  static final ConfigService _instance = ConfigService._internal();
  factory ConfigService() => _instance;
  ConfigService._internal();

  final EncryptionService _encryptionService = EncryptionService();
  final SecurityService _securityService = SecurityService();
  
  Map<String, dynamic>? _configCache;
  String? _cachedBotToken;
  String? _appToken;

  /// Инициализация сервиса конфигурации
  Future<void> initialize() async {
    // Проверяем безопасность окружения
    if (!await _securityService.isEnvironmentSafe()) {
      throw Exception('Unsafe environment detected');
    }

    // Загружаем кешированную конфигурацию
    await _loadCachedConfig();

    // Аутентифицируем приложение на сервере
    await _authenticateApp();

    // Обновляем конфигурацию с сервера
    await refreshConfig();
  }

  /// Аутентификация приложения на сервере
  Future<void> _authenticateApp() async {
    try {
      final packageInfo = await PackageInfo.fromPlatform();
      final appVersion = packageInfo.version;
      
      // Генерируем подпись приложения
      final signature = _generateAppSignature(appVersion);
      
      final response = await http.post(
        Uri.parse('$_baseUrl/api/auth/app'),
        headers: {
          'app-version': appVersion,
          'app-signature': signature,
          'device-id': await _getDeviceId(),
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _appToken = data['token'];
        
        // Сохраняем токен
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_appTokenKey, _appToken!);
      } else {
        throw Exception('Failed to authenticate app: ${response.statusCode}');
      }
    } catch (e) {
      print('App authentication error: $e');
      // Используем сохраненный токен если есть
      final prefs = await SharedPreferences.getInstance();
      _appToken = prefs.getString(_appTokenKey);
    }
  }

  /// Генерация подписи приложения
  String _generateAppSignature(String appVersion) {
    // В production используйте секретный ключ из secure storage
    const secretKey = 'your-secret-key-change-this';
    final bytes = utf8.encode('$appVersion:$secretKey');
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  /// Получение ID устройства
  Future<String> _getDeviceId() async {
    // Здесь должна быть реальная логика получения уникального ID устройства
    // Например, используя device_info_plus
    return 'device_${DateTime.now().millisecondsSinceEpoch}';
  }

  /// Обновление конфигурации с сервера
  Future<void> refreshConfig() async {
    if (_appToken == null) {
      await _authenticateApp();
      if (_appToken == null) {
        throw Exception('No app token available');
      }
    }

    try {
      final packageInfo = await PackageInfo.fromPlatform();
      
      final response = await http.get(
        Uri.parse('$_baseUrl/api/config'),
        headers: {
          'Authorization': 'Bearer $_appToken',
          'X-App-Version': packageInfo.version,
        },
      );

      if (response.statusCode == 200) {
        final config = json.decode(response.body);
        
        // Проверяем подпись конфигурации
        if (_verifyConfigSignature(config)) {
          _configCache = config;
          await _saveConfigToCache(config);
        } else {
          throw Exception('Invalid config signature');
        }
      } else if (response.statusCode == 401) {
        // Токен истек, переаутентифицируемся
        await _authenticateApp();
        return refreshConfig(); // Рекурсивный вызов
      } else {
        throw Exception('Failed to fetch config: ${response.statusCode}');
      }
    } catch (e) {
      print('Config refresh error: $e');
      // Используем кешированную конфигурацию
      if (_configCache == null) {
        throw Exception('No cached config available');
      }
    }
  }

  /// Проверка подписи конфигурации
  bool _verifyConfigSignature(Map<String, dynamic> config) {
    final signature = config['signature'];
    if (signature == null) return false;

    // Создаем копию без подписи для проверки
    final configCopy = Map<String, dynamic>.from(config);
    configCopy.remove('signature');
    configCopy.remove('timestamp');

    // Сортируем и сериализуем
    final configString = _sortedJsonEncode(configCopy);
    
    // Проверяем подпись (используйте тот же секрет что и на сервере)
    const secretKey = 'your-secret-key-change-this';
    final bytes = utf8.encode('$configString:$secretKey');
    final digest = sha256.convert(bytes);
    
    return digest.toString() == signature;
  }

  /// Сериализация JSON с сортировкой ключей
  String _sortedJsonEncode(dynamic obj) {
    if (obj is Map) {
      final sortedKeys = obj.keys.toList()..sort();
      final sortedMap = {
        for (var key in sortedKeys) key: obj[key],
      };
      return json.encode(sortedMap);
    }
    return json.encode(obj);
  }

  /// Получение токена бота
  Future<String> getBotToken({required String userId}) async {
    // Проверяем кеш
    if (_cachedBotToken != null) {
      return _cachedBotToken!;
    }

    if (_appToken == null) {
      throw Exception('App not authenticated');
    }

    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/bot-token'),
        headers: {
          'Authorization': 'Bearer $_appToken',
          'user-id': userId,
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final encryptedToken = data['token'];
        
        // Расшифровываем токен
        final decryptedToken = _decryptToken(encryptedToken, userId);
        
        // Кешируем на время, указанное сервером
        _cachedBotToken = decryptedToken;
        
        // Устанавливаем таймер для очистки кеша
        final expiresIn = data['expires_in'] ?? 3600;
        Future.delayed(Duration(seconds: expiresIn), () {
          _cachedBotToken = null;
        });
        
        return decryptedToken;
      } else {
        throw Exception('Failed to get bot token: ${response.statusCode}');
      }
    } catch (e) {
      print('Bot token fetch error: $e');
      // В крайнем случае можно использовать fallback (НЕ рекомендуется для production)
      throw Exception('Cannot retrieve bot token');
    }
  }

  /// Расшифровка токена (простой XOR, как на сервере)
  String _decryptToken(String encryptedToken, String key) {
    final encrypted = base64.decode(encryptedToken);
    final keyHash = sha256.convert(utf8.encode(key)).bytes;
    
    final decrypted = List<int>.generate(encrypted.length, (i) {
      return encrypted[i] ^ keyHash[i % keyHash.length];
    });
    
    return utf8.decode(decrypted);
  }

  /// Загрузка кешированной конфигурации
  Future<void> _loadCachedConfig() async {
    final prefs = await SharedPreferences.getInstance();
    final cachedConfig = prefs.getString(_configCacheKey);
    final timestamp = prefs.getInt(_configTimestampKey) ?? 0;
    
    if (cachedConfig != null) {
      final now = DateTime.now().millisecondsSinceEpoch;
      final age = (now - timestamp) ~/ 60000; // минуты
      
      if (age < _cacheValidityMinutes) {
        _configCache = json.decode(cachedConfig);
      }
    }
  }

  /// Сохранение конфигурации в кеш
  Future<void> _saveConfigToCache(Map<String, dynamic> config) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_configCacheKey, json.encode(config));
    await prefs.setInt(_configTimestampKey, DateTime.now().millisecondsSinceEpoch);
  }

  /// Получение списка каналов для мониторинга
  List<String> get monitoringChannels {
    return List<String>.from(_configCache?['monitoring_channels'] ?? [
      '@News_Collections',
      '@gifts_detector',
      '@GiftsTracker',
      '@new_gifts_alert_news'
    ]);
  }

  /// Получение URL API
  String get apiUrl {
    return _configCache?['api_url'] ?? _baseUrl;
  }

  /// Проверка, включен ли фоновый мониторинг
  bool get isBackgroundMonitoringEnabled {
    return _configCache?['features']?['background_monitoring'] ?? true;
  }

  /// Получение максимальной цены для фильтрации
  int get maxPriceFilter {
    return _configCache?['features']?['max_price_filter'] ?? 100000;
  }

  /// Проверка необходимости обновления приложения
  bool get isUpdateRequired {
    return _configCache?['security']?['force_update'] ?? false;
  }

  /// Получение минимальной версии приложения
  String get minAppVersion {
    return _configCache?['security']?['min_app_version'] ?? '1.0.0';
  }

  /// Очистка всех данных
  Future<void> clearAll() async {
    _configCache = null;
    _cachedBotToken = null;
    _appToken = null;
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_configCacheKey);
    await prefs.remove(_configTimestampKey);
    await prefs.remove(_appTokenKey);
  }
}