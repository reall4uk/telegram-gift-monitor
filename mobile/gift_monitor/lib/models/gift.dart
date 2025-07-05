import 'package:flutter/material.dart';

class Gift {
  final String id;
  final String? name;
  final String price;
  final int? total;
  final int? available;
  final double? availablePercent;
  final bool isLimited;
  final bool isSoldOut;
  final String? emoji;
  final DateTime detectedAt;
  final double urgencyScore;

  Gift({
    required this.id,
    this.name,
    required this.price,
    this.total,
    this.available,
    this.availablePercent,
    required this.isLimited,
    required this.isSoldOut,
    this.emoji,
    required this.detectedAt,
    this.urgencyScore = 0.5,
  });

  factory Gift.fromJson(Map<String, dynamic> json) {
    // Parse gift data from API response
    final giftData = json['gift_data'] ?? {};
    
    return Gift(
      id: giftData['id'] ?? json['gift_id'] ?? '',
      name: giftData['name'],
      price: giftData['price'] ?? '0',
      total: giftData['total'],
      available: giftData['available'],
      availablePercent: giftData['available_percent']?.toDouble(),
      isLimited: giftData['is_limited'] ?? false,
      isSoldOut: giftData['is_sold_out'] ?? false,
      emoji: giftData['emoji'],
      detectedAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      urgencyScore: giftData['urgency_score']?.toDouble() ?? 0.5,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'price': price,
      'total': total,
      'available': available,
      'available_percent': availablePercent,
      'is_limited': isLimited,
      'is_sold_out': isSoldOut,
      'emoji': emoji,
      'detected_at': detectedAt.toIso8601String(),
      'urgency_score': urgencyScore,
    };
  }

  // Helper method to get urgency color
  Color get urgencyColor {
    if (urgencyScore > 0.7) return const Color(0xFFFF4444); // Red
    if (urgencyScore > 0.4) return const Color(0xFFFFAA00); // Orange
    return const Color(0xFF44AA00); // Green
  }
}