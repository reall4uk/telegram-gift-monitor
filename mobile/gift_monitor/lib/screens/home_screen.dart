import 'package:flutter/material.dart';
import 'dart:async';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/gift.dart';
import '../services/api_service.dart';
import '../services/notification_service.dart';
import '../services/background_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  final _apiService = ApiService();
  final _notificationService = NotificationService();
  
  List<Gift> _recentGifts = [];
  bool _isLoading = true;
  bool _notificationsEnabled = false;
  Timer? _refreshTimer;
  Set<String> _seenGiftIds = {};
  bool _isFirstLoad = true;
  
  // Интервал обновления - 30 секунд (синхронизирован с фоновым сервисом)
  static const Duration _refreshInterval = Duration(seconds: 30);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initializeApp();
    _startAutoRefresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _refreshTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Управляем таймером в зависимости от состояния приложения
    if (state == AppLifecycleState.resumed) {
      _startAutoRefresh();
      _loadRecentGifts(); // Обновляем при возврате в приложение
    } else if (state == AppLifecycleState.paused) {
      _refreshTimer?.cancel();
    }
  }

  /// Запуск автообновления
  void _startAutoRefresh() {
    _refreshTimer?.cancel();
    _refreshTimer = Timer.periodic(_refreshInterval, (timer) {
      if (mounted) {
        _loadRecentGifts(showLoading: false);
      }
    });
  }

  /// Инициализация приложения
  Future<void> _initializeApp() async {
    await _notificationService.initialize();
    
    // Загружаем настройки
    final prefs = await SharedPreferences.getInstance();
    final seenIds = prefs.getStringList('seen_gift_ids') ?? [];
    _seenGiftIds = seenIds.toSet();
    _notificationsEnabled = prefs.getBool('notifications_enabled') ?? false;
    
    // Проверяем статус фонового сервиса
    final backgroundEnabled = prefs.getBool('background_enabled') ?? false;
    if (backgroundEnabled) {
      final isRunning = await BackgroundService.isBackgroundServiceRunning();
      print('[HomeScreen] Фоновый сервис включен в настройках: $backgroundEnabled, работает: $isRunning');
      if (!isRunning) {
        await BackgroundService.startBackgroundMonitoring();
      }
    }
    
    await _loadRecentGifts();
  }

  /// Загрузка последних подарков
  Future<void> _loadRecentGifts({bool showLoading = true}) async {
    if (showLoading && mounted) {
      setState(() => _isLoading = true);
    }
    
    try {
      final gifts = await _apiService.getRecentGifts();
      
      if (!mounted) return;
      
      // Находим новые подарки
      final newGifts = <Gift>[];
      for (var gift in gifts) {
        if (!_seenGiftIds.contains(gift.id)) {
          _seenGiftIds.add(gift.id);
          newGifts.add(gift);
        }
      }
      
      setState(() {
        _recentGifts = gifts;
        _isLoading = false;
      });
      
      // Сохраняем виденные подарки
      if (_seenGiftIds.isNotEmpty) {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setStringList('seen_gift_ids', _seenGiftIds.toList());
      }
      
      // Показываем уведомления для новых подарков
      if (!_isFirstLoad && newGifts.isNotEmpty && _notificationsEnabled) {
        await _showNotificationsForNewGifts(newGifts);
      }
      
      _isFirstLoad = false;
      
    } catch (e) {
      print('[HomeScreen] Ошибка загрузки подарков: $e');
      if (mounted && showLoading) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Ошибка загрузки: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  /// Показ уведомлений для новых подарков
  Future<void> _showNotificationsForNewGifts(List<Gift> newGifts) async {
    final prefs = await SharedPreferences.getInstance();
    final minPrice = prefs.getDouble('min_price') ?? 0; // Изменено на getDouble
    
    for (var gift in newGifts) {
      // Применяем фильтр по цене
      final priceString = gift.price.replaceAll(',', '').replaceAll(' ', '');
      final price = double.tryParse(priceString) ?? 0;
      if (price < minPrice) continue;
      
      // Показываем уведомление (price теперь String)
      await _notificationService.showGiftNotification(
        giftId: gift.id,
        price: gift.price, // Передаем как String
        title: gift.name ?? 'Новый подарок!',
        isLimited: gift.isLimited,
      );
      
      // Показываем снэкбар в приложении
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('🎁 ${gift.name ?? gift.id.substring(0, 8)} - ${gift.price} ⭐'),
            backgroundColor: Colors.orange,
            duration: const Duration(seconds: 5),
            action: SnackBarAction(
              label: 'Посмотреть',
              textColor: Colors.white,
              onPressed: () {
                // Прокрутка к подарку
                final index = _recentGifts.indexWhere((g) => g.id == gift.id);
                if (index != -1) {
                  // TODO: добавить прокрутку к элементу
                }
              },
            ),
          ),
        );
      }
    }
  }

  /// Переключение уведомлений
  Future<void> _toggleNotifications() async {
    final prefs = await SharedPreferences.getInstance();
    
    if (_notificationsEnabled) {
      // Отключаем уведомления
      setState(() => _notificationsEnabled = false);
      await prefs.setBool('notifications_enabled', false);
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Уведомления отключены'),
            backgroundColor: Colors.orange,
            duration: Duration(seconds: 2),
          ),
        );
      }
    } else {
      // Запрашиваем разрешение на уведомления
      final granted = await _notificationService.requestPermission();
      setState(() => _notificationsEnabled = granted);
      await prefs.setBool('notifications_enabled', granted);
      
      if (granted && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Уведомления включены!'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 2),
          ),
        );
      } else if (!granted && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Разрешение на уведомления не получено'),
            backgroundColor: Colors.red,
            duration: Duration(seconds: 3),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E2336),
        title: Row(
          children: [
            const Text('Gift Monitor', style: TextStyle(color: Colors.white)),
            const SizedBox(width: 8),
            if (!_isLoading && !_isFirstLoad)
              Tooltip(
                message: 'Автообновление каждые 30 секунд',
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: Colors.greenAccent,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.greenAccent.withOpacity(0.8),
                        blurRadius: 8,
                        spreadRadius: 2,
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(
              _notificationsEnabled ? Icons.notifications_active : Icons.notifications_off,
              color: _notificationsEnabled ? Colors.blueAccent : Colors.grey,
            ),
            onPressed: _toggleNotifications,
            tooltip: _notificationsEnabled ? 'Уведомления включены' : 'Уведомления выключены',
          ),
          IconButton(
            icon: const Icon(Icons.alarm, color: Colors.white),
            onPressed: () async {
              await _notificationService.showTestNotification();
            },
            tooltip: 'Тест уведомления',
          ),
          IconButton(
            icon: const Icon(Icons.bug_report, color: Colors.orange),
            onPressed: () async {
              // Отладочная информация
              final isRunning = await BackgroundService.isBackgroundServiceRunning();
              final prefs = await SharedPreferences.getInstance();
              final backgroundEnabled = prefs.getBool('background_enabled') ?? false;
              
              if (mounted) {
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Статус фонового сервиса'),
                    content: Text(
                      'Включен в настройках: $backgroundEnabled\n'
                      'Сервис работает: $isRunning\n'
                      'Уведомления: $_notificationsEnabled',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('OK'),
                      ),
                    ],
                  ),
                );
              }
            },
            tooltip: 'Отладка',
          ),
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white),
            onPressed: () => Navigator.pushNamed(context, '/settings').then((_) {
              // Перезагружаем настройки после возврата
              _initializeApp();
            }),
            tooltip: 'Настройки',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _loadRecentGifts(showLoading: false),
        child: _isLoading && _isFirstLoad
            ? const Center(child: CircularProgressIndicator(color: Colors.blueAccent))
            : _recentGifts.isEmpty
                ? _buildEmptyState()
                : _buildGiftList(),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.card_giftcard,
            size: 80,
            color: Colors.grey[600],
          ),
          const SizedBox(height: 16),
          Text(
            'Нет новых подарков',
            style: TextStyle(
              color: Colors.grey[400],
              fontSize: 18,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Автообновление каждые 30 секунд',
            style: TextStyle(
              color: Colors.grey[600],
              fontSize: 14,
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => _loadRecentGifts(),
            icon: const Icon(Icons.refresh),
            label: const Text('Обновить'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.blueAccent,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGiftList() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _recentGifts.length,
      itemBuilder: (context, index) {
        final gift = _recentGifts[index];
        return _buildGiftCard(gift);
      },
    );
  }

  Widget _buildGiftCard(Gift gift) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E2336),
        borderRadius: BorderRadius.circular(16),
        border: gift.isSoldOut
            ? Border.all(color: Colors.red.withOpacity(0.5), width: 2)
            : gift.isLimited
                ? Border.all(color: Colors.orange.withOpacity(0.5), width: 2)
                : Border.all(color: Colors.blueAccent.withOpacity(0.5), width: 2),
      ),
      child: InkWell(
        onTap: () {
          // TODO: открыть детали подарка
        },
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    gift.emoji ?? '🎁',
                    style: const TextStyle(fontSize: 32),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          gift.name ?? 'Подарок #${gift.id.substring(0, 8)}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(
                              Icons.star,
                              size: 16,
                              color: Colors.amber[400],
                            ),
                            const SizedBox(width: 4),
                            Text(
                              gift.price,
                              style: TextStyle(
                                color: Colors.amber[400],
                                fontSize: 16,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  _buildStatusBadge(gift),
                ],
              ),
              if (gift.total != null) ...[
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Всего: ${gift.total}',
                      style: TextStyle(color: Colors.grey[400], fontSize: 14),
                    ),
                    if (gift.available != null)
                      Text(
                        'Доступно: ${gift.available}',
                        style: TextStyle(
                          color: gift.available! > 0 ? Colors.greenAccent : Colors.redAccent,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                if (gift.availablePercent != null)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: gift.availablePercent! / 100,
                      backgroundColor: Colors.grey[800],
                      valueColor: AlwaysStoppedAnimation<Color>(
                        gift.availablePercent! > 50
                            ? Colors.greenAccent
                            : gift.availablePercent! > 20
                                ? Colors.orangeAccent
                                : Colors.redAccent,
                      ),
                      minHeight: 6,
                    ),
                  ),
              ],
              const SizedBox(height: 8),
              Text(
                'Обнаружен: ${_formatDate(gift.detectedAt)}',
                style: TextStyle(color: Colors.grey[600], fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusBadge(Gift gift) {
    if (gift.isSoldOut) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.red.withOpacity(0.2),
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Text(
          'Распродан',
          style: TextStyle(
            color: Colors.redAccent,
            fontSize: 12,
            fontWeight: FontWeight.bold,
          ),
        ),
      );
    } else if (gift.isLimited) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.orange.withOpacity(0.2),
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Text(
          'Лимитированный',
          style: TextStyle(
            color: Colors.orangeAccent,
            fontSize: 12,
            fontWeight: FontWeight.bold,
          ),
        ),
      );
    } else {
      return const SizedBox.shrink();
    }
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);
    
    if (difference.inMinutes < 1) {
      return 'только что';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes} мин. назад';
    } else if (difference.inHours < 24) {
      return '${difference.inHours} ч. назад';
    } else {
      return '${difference.inDays} дн. назад';
    }
  }
}