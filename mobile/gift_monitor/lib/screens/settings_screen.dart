import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/notification_service.dart';
import '../services/background_service.dart';
import '../services/telegram_auth_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  // Состояния настроек
  bool _soundEnabled = true;
  bool _vibrationEnabled = true;
  bool _limitedOnly = true; // Все подарки лимитированные
  double _minPrice = 0; // Изменено на double
  String _selectedSound = 'default';
  double _soundVolume = 1.0;
  bool _backgroundEnabled = false;
  
  // Каналы для мониторинга
  final List<String> _allChannels = [
    '@News_Collections',
    '@gifts_detector', 
    '@GiftsTracker',
    '@new_gifts_alert_news',
  ];
  
  List<String> _selectedChannels = [];
  
  // Шаги для фильтра цены
  final List<double> _priceSteps = [ // Изменено на double
    0, 50, 100, 150, 200, 250, 300, 500, 1000, 2000, 5000, 10000
  ];
  
  // Доступные звуки (без дубликата уведомление/стандартный)
  final Map<String, String> _availableSounds = {
    'default': 'Стандартный',
    'alarm': 'Будильник',
    'ringtone': 'Рингтон',
  };

  late SharedPreferences _prefs;
  final NotificationService _notificationService = NotificationService();
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  /// Загрузка всех настроек
  Future<void> _loadSettings() async {
    _prefs = await SharedPreferences.getInstance();
    
    setState(() {
      _soundEnabled = _prefs.getBool('sound_enabled') ?? true;
      _vibrationEnabled = _prefs.getBool('vibration_enabled') ?? true;
      _limitedOnly = _prefs.getBool('limited_only') ?? true;
      _minPrice = _prefs.getDouble('min_price') ?? 0; // Изменено на getDouble
      _selectedSound = _prefs.getString('notification_sound') ?? 'default';
      _soundVolume = _prefs.getDouble('notification_volume') ?? 1.0;
      _backgroundEnabled = _prefs.getBool('background_enabled') ?? false;
      
      // Загружаем выбранные каналы
      final channels = _prefs.getStringList('selected_channels');
      if (channels != null && channels.isNotEmpty) {
        _selectedChannels = List.from(channels);
      } else {
        _selectedChannels = List.from(_allChannels); // По умолчанию все
      }
      
      _isLoading = false;
    });
  }

  /// Сохранение всех настроек
  Future<void> _saveAllSettings() async {
    await _prefs.setBool('sound_enabled', _soundEnabled);
    await _prefs.setBool('vibration_enabled', _vibrationEnabled);
    await _prefs.setBool('limited_only', _limitedOnly);
    await _prefs.setDouble('min_price', _minPrice); // Изменено на setDouble
    await _prefs.setString('notification_sound', _selectedSound);
    await _prefs.setDouble('notification_volume', _soundVolume);
    await _prefs.setBool('background_enabled', _backgroundEnabled);
    await _prefs.setStringList('selected_channels', _selectedChannels);
    
    // Сохраняем настройки уведомлений
    await _notificationService.saveNotificationSettings(
      soundEnabled: _soundEnabled,
      vibrationEnabled: _vibrationEnabled,
      soundType: _selectedSound,
      volume: _soundVolume,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        backgroundColor: Color(0xFF0A0E21),
        body: Center(child: CircularProgressIndicator()),
      );
    }
    
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E2336),
        title: const Text('Настройки', style: TextStyle(color: Colors.white)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildSectionTitle('Уведомления'),
          _buildSwitch(
            'Звук',
            'Воспроизводить звук при новом подарке',
            _soundEnabled,
            (value) async {
              setState(() => _soundEnabled = value);
              await _saveAllSettings();
            },
          ),
          _buildSwitch(
            'Вибрация',
            'Вибрация при уведомлении',
            _vibrationEnabled,
            (value) async {
              setState(() => _vibrationEnabled = value);
              await _saveAllSettings();
            },
          ),
          
          const SizedBox(height: 24),
          _buildSectionTitle('Настройки звука'),
          _buildSoundSelector(),
          _buildTestButton(),
          
          const SizedBox(height: 24),
          _buildSectionTitle('Фоновая работа'),
          _buildSwitch(
            'Мониторинг в фоне',
            'Проверять новые подарки даже когда приложение закрыто',
            _backgroundEnabled,
            (value) async {
              setState(() => _backgroundEnabled = value);
              await _saveAllSettings();
              
              if (value) {
                await BackgroundService.startBackgroundMonitoring(); // Исправлено
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Фоновый мониторинг включен'),
                      backgroundColor: Colors.green,
                      duration: Duration(seconds: 2),
                    ),
                  );
                }
              } else {
                await BackgroundService.stopBackgroundMonitoring(); // Исправлено
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Фоновый мониторинг выключен'),
                      backgroundColor: Colors.orange,
                      duration: Duration(seconds: 2),
                    ),
                  );
                }
              }
            },
          ),
          
          const SizedBox(height: 24),
          _buildSectionTitle('Фильтры подарков'),
          _buildPriceFilter(),
          
          const SizedBox(height: 24),
          _buildSectionTitle('Отслеживаемые каналы'),
          _buildChannelsList(),
          
          const SizedBox(height: 24),
          _buildLogoutButton(),
          
          const SizedBox(height: 40),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Text(
        title,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 20,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildSwitch(String title, String subtitle, bool value, Function(bool) onChanged) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E2336),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: TextStyle(
                    color: Colors.grey[400],
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: Colors.blueAccent,
          ),
        ],
      ),
    );
  }

  Widget _buildSoundSelector() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E2336),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Тип звука',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: _selectedSound,
            decoration: InputDecoration(
              filled: true,
              fillColor: const Color(0xFF0A0E21),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide.none,
              ),
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            ),
            dropdownColor: const Color(0xFF1E2336),
            style: const TextStyle(color: Colors.white),
            items: _availableSounds.entries.map((entry) {
              return DropdownMenuItem<String>(
                value: entry.key,
                child: Row(
                  children: [
                    Icon(
                      _getSoundIcon(entry.key),
                      color: Colors.blueAccent,
                      size: 20,
                    ),
                    const SizedBox(width: 12),
                    Text(entry.value),
                  ],
                ),
              );
            }).toList(),
            onChanged: (value) async {
              if (value != null) {
                setState(() => _selectedSound = value);
                await _saveAllSettings();
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _buildTestButton() {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      child: ElevatedButton.icon(
        onPressed: () async {
          await _notificationService.showTestNotification(
            soundType: _selectedSound,
            volume: _soundVolume,
            // Убрали vibrationEnabled - его нет в методе
          );
        },
        icon: const Icon(Icons.notifications_active),
        label: const Text('Тест уведомления'),
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.blueAccent,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
    );
  }

  Widget _buildPriceFilter() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E2336),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Минимальная цена',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Уведомлять о подарках от ${_minPrice.toStringAsFixed(0)} ⭐', // Форматирование для отображения
            style: TextStyle(
              color: Colors.grey[400],
              fontSize: 14,
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _priceSteps.map((price) {
              final isSelected = _minPrice == price;
              return ChoiceChip(
                label: Text(
                  price == 0 ? 'Все' : price.toStringAsFixed(0), // Форматирование
                  style: TextStyle(
                    color: isSelected ? Colors.white : Colors.grey[400],
                    fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
                selected: isSelected,
                onSelected: (selected) async {
                  if (selected) {
                    setState(() => _minPrice = price);
                    await _saveAllSettings();
                  }
                },
                selectedColor: Colors.blueAccent,
                backgroundColor: const Color(0xFF0A0E21),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                  side: BorderSide(
                    color: isSelected ? Colors.blueAccent : Colors.grey[600]!,
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildChannelsList() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E2336),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Выбрано каналов:',
                style: TextStyle(color: Colors.white, fontSize: 14),
              ),
              Text(
                '${_selectedChannels.length} из ${_allChannels.length}',
                style: const TextStyle(
                  color: Colors.blueAccent,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ..._allChannels.map((channel) {
            final isSelected = _selectedChannels.contains(channel);
            return CheckboxListTile(
              value: isSelected,
              onChanged: (value) async {
                setState(() {
                  if (value ?? false) {
                    _selectedChannels.add(channel);
                  } else {
                    _selectedChannels.remove(channel);
                  }
                });
                await _saveAllSettings();
              },
              title: Text(
                channel,
                style: const TextStyle(color: Colors.white),
              ),
              activeColor: Colors.blueAccent,
              checkColor: Colors.white,
              controlAffinity: ListTileControlAffinity.leading,
              contentPadding: EdgeInsets.zero,
              dense: true,
            );
          }).toList(),
        ],
      ),
    );
  }

  Widget _buildLogoutButton() {
    return ElevatedButton.icon(
      onPressed: () {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            backgroundColor: const Color(0xFF1E2336),
            title: const Text(
              'Выход',
              style: TextStyle(color: Colors.white),
            ),
            content: const Text(
              'Вы уверены, что хотите выйти?',
              style: TextStyle(color: Colors.grey),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Отмена'),
              ),
              TextButton(
                onPressed: () async {
                  // Останавливаем фоновый сервис
                  await BackgroundService.stopBackgroundMonitoring();
                  
                  // ВАЖНО: Очищаем авторизацию
                  await TelegramAuthService.logout();
                  
                  if (mounted) {
                    // Закрываем диалог
                    Navigator.of(context).pop();
                    
                    // Переходим на экран авторизации
                    Navigator.of(context).pushNamedAndRemoveUntil(
                      '/',
                      (route) => false,
                    );
                  }
                },
                child: const Text(
                  'Выйти',
                  style: TextStyle(color: Colors.redAccent),
                ),
              ),
            ],
          ),
        );
      },
      icon: const Icon(Icons.logout),
      label: const Text('Выйти из аккаунта'),
      style: ElevatedButton.styleFrom(
        backgroundColor: Colors.red.withOpacity(0.2),
        foregroundColor: Colors.redAccent,
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }
  
  IconData _getSoundIcon(String soundType) {
    switch (soundType) {
      case 'alarm':
        return Icons.alarm;
      case 'ringtone':
        return Icons.phone_in_talk;
      default:
        return Icons.notifications;
    }
  }
}