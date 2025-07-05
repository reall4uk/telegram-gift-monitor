import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/gift.dart';

class ApiService {
  static const String baseUrl = 'http://192.168.0.103:8000'; // Замените на IP вашего компьютера
  String? _authToken;

  // Singleton pattern
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  // Get recent gifts
  Future<List<Gift>> getRecentGifts() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/v1/gifts/recent'),
        headers: _authToken != null ? {'Authorization': 'Bearer $_authToken'} : {},
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.map((json) => Gift.fromJson(json)).toList();
      } else {
        throw Exception('Failed to load gifts');
      }
    } catch (e) {
      print('Error getting recent gifts: $e');
      // Return mock data for testing
      return _getMockGifts();
    }
  }

  // Mock data for testing
  List<Gift> _getMockGifts() {
    return [
      Gift(
        id: '1234567890',
        name: 'Premium Gift',
        price: '5,000',
        total: 10000,
        available: 250,
        availablePercent: 2.5,
        isLimited: true,
        isSoldOut: false,
        emoji: '🎁',
        detectedAt: DateTime.now().subtract(const Duration(minutes: 5)),
        urgencyScore: 0.8,
      ),
      Gift(
        id: '0987654321',
        name: 'Rare Drop',
        price: '10,000',
        total: 1000,
        available: 0,
        availablePercent: 0,
        isLimited: true,
        isSoldOut: true,
        emoji: '💎',
        detectedAt: DateTime.now().subtract(const Duration(hours: 2)),
        urgencyScore: 0.3,
      ),
    ];
  }

  // Send verification code
  Future<void> sendVerificationCode(String phone) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/v1/auth/send-code'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'phone': phone}),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to send code');
      }
    } catch (e) {
      print('Error sending code: $e');
      // For testing, don't throw error
    }
  }

  // Verify code
  Future<void> verifyCode(String phone, String code) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/v1/auth/verify'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'phone': phone, 'code': code}),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _authToken = data['token'];
      } else {
        throw Exception('Invalid code');
      }
    } catch (e) {
      print('Error verifying code: $e');
      // For testing, don't throw error
    }
  }

  // Get user profile
  Future<Map<String, dynamic>> getUserProfile() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/v1/user/profile'),
        headers: {'Authorization': 'Bearer $_authToken'},
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to load profile');
      }
    } catch (e) {
      print('Error loading profile: $e');
      return {'phone': '+7 999 123-45-67', 'subscription': 'active'};
    }
  }

  // Update settings
  Future<void> updateSettings(Map<String, dynamic> settings) async {
    try {
      final response = await http.put(
        Uri.parse('$baseUrl/api/v1/user/settings'),
        headers: {
          'Authorization': 'Bearer $_authToken',
          'Content-Type': 'application/json',
        },
        body: json.encode(settings),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to update settings');
      }
    } catch (e) {
      print('Error updating settings: $e');
    }
  }

  // Logout
  void logout() {
    _authToken = null;
  }
}