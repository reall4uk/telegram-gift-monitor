import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/telegram_auth_service.dart';
import 'package:url_launcher/url_launcher.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({Key? key}) : super(key: key);

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _formKey = GlobalKey<FormState>();
  final _userIdController = TextEditingController();
  bool _isLoading = false;
  String _errorMessage = '';
  String _requiredChannel = '@analizatorNFT'; // Значение по умолчанию

  @override
  void initState() {
    super.initState();
    _loadRequiredChannel();
  }
  
  Future<void> _loadRequiredChannel() async {
    final channel = await TelegramAuthService.requiredChannel;
    if (mounted) {
      setState(() {
        _requiredChannel = channel;
      });
    }
  }

  @override
  void dispose() {
    _userIdController.dispose();
    super.dispose();
  }

  Future<void> _openTelegramChannel(String channel) async {
    final url = 'https://t.me/${channel.substring(1)}'; // Убираем @
    if (await canLaunchUrl(Uri.parse(url))) {
      await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    }
  }

  Future<void> _openUserIdBot() async {
    const url = 'https://t.me/userinfobot';
    if (await canLaunchUrl(Uri.parse(url))) {
      await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    }
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final userId = _userIdController.text.trim();
      
      // Проверяем подписку на канал
      final isSubscribed = await TelegramAuthService.checkSubscription(userId);
      
      if (!isSubscribed) {
        setState(() {
          _errorMessage = 'Вы не подписаны на канал $_requiredChannel!\nПодпишитесь и попробуйте снова.';
          _isLoading = false;
        });
        return;
      }
      
      // Сохраняем авторизацию
      await TelegramAuthService.saveAuth(userId);
      
      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/home');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Ошибка авторизации: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1a1a2e),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Logo
                  const Icon(
                    Icons.card_giftcard,
                    size: 80,
                    color: Color(0xFF4ecdc4),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Gift Monitor',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Мониторинг подарков в Telegram',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.white60,
                    ),
                  ),
                  
                  const SizedBox(height: 48),
                  
                  // Инструкция
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF16213e),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFF4ecdc4).withOpacity(0.3)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '📋 Для использования приложения:',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          '1. Подпишитесь на канал ниже\n'
                          '2. Узнайте ваш Telegram User ID\n'
                          '3. Введите User ID для входа',
                          style: TextStyle(color: Colors.white70, height: 1.5),
                        ),
                      ],
                    ),
                  ),
                  
                  const SizedBox(height: 24),
                  
                  // Канал для подписки
                  const Text(
                    'Канал для доступа:',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  InkWell(
                    onTap: () => _openTelegramChannel(_requiredChannel),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF16213e),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF4ecdc4).withOpacity(0.5)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.telegram, color: Color(0xFF4ecdc4), size: 24),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Analizator NFT',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  _requiredChannel,
                                  style: const TextStyle(color: Colors.white54, fontSize: 14),
                                ),
                              ],
                            ),
                          ),
                          const Icon(Icons.open_in_new, color: Color(0xFF4ecdc4), size: 20),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 24),
                  
                  // Как узнать User ID
                  InkWell(
                    onTap: _openUserIdBot,
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF16213e).withOpacity(0.5),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF4ecdc4).withOpacity(0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.info_outline, color: Color(0xFF4ecdc4), size: 20),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '🔍 Как узнать User ID?',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                SizedBox(height: 4),
                                Text(
                                  'Нажмите здесь, чтобы открыть @userinfobot',
                                  style: TextStyle(color: Colors.white70, fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                          const Icon(Icons.open_in_new, color: Color(0xFF4ecdc4), size: 16),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 32),
                  
                  // User ID input
                  TextFormField(
                    controller: _userIdController,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: 'Telegram User ID',
                      hintText: 'Например: 123456789',
                      labelStyle: const TextStyle(color: Colors.white60),
                      hintStyle: const TextStyle(color: Colors.white30),
                      filled: true,
                      fillColor: const Color(0xFF16213e),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: const BorderSide(color: Color(0xFF4ecdc4)),
                      ),
                      prefixIcon: const Icon(Icons.person, color: Colors.white60),
                    ),
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Введите User ID';
                      }
                      if (!RegExp(r'^\d+$').hasMatch(value)) {
                        return 'User ID должен содержать только цифры';
                      }
                      return null;
                    },
                  ),
                  
                  if (_errorMessage.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.red.withOpacity(0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline, color: Colors.red, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _errorMessage,
                              style: const TextStyle(color: Colors.red, fontSize: 14),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  
                  const SizedBox(height: 24),
                  
                  // Login button
                  ElevatedButton(
                    onPressed: _isLoading ? null : _login,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF4ecdc4),
                      foregroundColor: const Color(0xFF1a1a2e),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      elevation: 0,
                    ),
                    child: _isLoading
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF1a1a2e)),
                            ),
                          )
                        : const Text(
                            'Войти',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Debug mode toggle (временно для разработки)
                  if (const bool.fromEnvironment('dart.vm.product') == false)
                    TextButton(
                      onPressed: () async {
                        // Режим разработки - вход без проверки
                        await TelegramAuthService.saveAuth('123456789');
                        if (mounted) {
                          Navigator.of(context).pushReplacementNamed('/home');
                        }
                      },
                      child: const Text(
                        'Войти без проверки (DEBUG)',
                        style: TextStyle(color: Colors.white38),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}