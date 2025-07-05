import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'screens/auth_screen.dart';
import 'screens/home_screen.dart';
import 'screens/settings_screen.dart';
import 'services/telegram_auth_service.dart';
import 'services/background_service.dart';
import 'services/notification_service.dart';
import 'services/security_service.dart';
import 'services/config_service.dart';

void main() async {
  // Инициализация Flutter
  WidgetsFlutterBinding.ensureInitialized();
  
  // Загрузка переменных окружения из .env файла
  await dotenv.load(fileName: ".env");
  
  // ВРЕМЕННО: Сброс авторизации для тестирования
  // final prefs = await SharedPreferences.getInstance();
  // await prefs.clear();
  // print('[Main] Авторизация сброшена');
  
  // ВАЖНО: Сначала инициализируем NotificationService и создаем каналы
  final notificationService = NotificationService();
  await notificationService.initialize();
  print('[Main] Каналы уведомлений созданы');
  
  // Только потом инициализируем фоновый сервис
  await BackgroundService.initialize();
  print('[Main] Фоновый сервис инициализирован');
  
  // Проверка безопасности приложения
  final isDebug = const bool.fromEnvironment('dart.vm.product') == false;
  
  if (!isDebug) {
    // В production режиме включаем все проверки
    final isSecure = await SecurityService.verifyAppIntegrity();
    if (!isSecure) {
      print('[Main] КРИТИЧНО: Обнаружены проблемы безопасности!');
      // TODO: Показать диалог и закрыть приложение
    }
  }
  
  // Инициализация ConfigService
  await ConfigService.initialize();
  print('[Main] ConfigService инициализирован');
  
  // Загрузка конфигурации с сервера
  try {
    await ConfigService.getConfig();
    print('[Main] Конфигурация загружена с сервера');
  } catch (e) {
    print('[Main] Используется локальная конфигурация: $e');
  }
  
  runApp(const GiftMonitorApp());
}

class GiftMonitorApp extends StatelessWidget {
  const GiftMonitorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Telegram Gift Monitor',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.deepPurple,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const AuthWrapper(),
      routes: {
        '/home': (context) => const HomeScreen(),
        '/settings': (context) => const SettingsScreen(),
      },
    );
  }
}

class AuthWrapper extends StatefulWidget {
  const AuthWrapper({super.key});

  @override
  State<AuthWrapper> createState() => _AuthWrapperState();
}

class _AuthWrapperState extends State<AuthWrapper> {
  bool _isAuthenticated = false;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _checkAuthStatus();
  }

  Future<void> _checkAuthStatus() async {
    // Проверяем сохраненную авторизацию
    final isAuth = await TelegramAuthService.isAuthorized();
    
    setState(() {
      _isAuthenticated = isAuth;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        backgroundColor: Color(0xFF1a1a2e),
        body: Center(
          child: CircularProgressIndicator(
            color: Color(0xFF4ecdc4),
          ),
        ),
      );
    }
    
    return _isAuthenticated ? const HomeScreen() : const AuthScreen();
  }
}