#!/usr/bin/env python3
"""
Gift Detector Module - Flexible Version
Detects gifts based on keywords without strict structure requirements
"""

import re
import logging
from typing import Dict, Optional, List
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class GiftDetector:
    """Detects and extracts gift information from messages"""
    
    def __init__(self):
        # Ключевые слова для определения подарка
        self.gift_keywords = [
            # Английские
            'gift', 'gifts', 'new gift', 'appeared', 'limited', 'rare',
            'exclusive', 'special', 'unique', 'premium', 'vip',
            # Русские
            'подарок', 'подарки', 'новый подарок', 'появился', 'редкий',
            'эксклюзив', 'особый', 'уникальный', 'премиум', 'вип',
            # Эмодзи
            '🎁', '🎀', '💎', '🎯', '🌟', '⭐', '🔥', '💰', '🏆'
        ]
        
        # Ключевые слова для лимитированных подарков
        self.limited_keywords = [
            'limited', 'rare', 'exclusive', 'special', 'unique', 'vip',
            'лимит', 'редкий', 'эксклюзив', 'особый', 'уникальный', 'вип',
            '🔥', '⚡', '💎'
        ]
        
        # Паттерны для извлечения чисел (ID, цены и т.д.)
        self.number_patterns = [
            r'\b(\d{10,20})\b',  # Длинные числа (вероятно ID)
            r'(\d{1,3}(?:,\d{3})*)',  # Числа с запятыми (цены)
            r'(\d+(?:\.\d+)?)',  # Обычные числа
        ]
    
    def detect_gift(self, text: str) -> Optional[Dict]:
        """
        Гибкое определение подарка в сообщении
        
        Args:
            text: Текст сообщения
            
        Returns:
            Dict с данными подарка или None
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Проверяем наличие ключевых слов
        has_gift_keyword = any(keyword in text_lower for keyword in self.gift_keywords)
        
        if not has_gift_keyword:
            return None
        
        # Создаем уникальный ID на основе текста и времени
        gift_id = self._generate_gift_id(text)
        
        gift_data = {
            'id': gift_id,
            'detected_at': datetime.utcnow().isoformat(),
            'is_limited': self._is_limited_gift(text_lower),
            'is_sold_out': self._is_sold_out(text_lower),
            'urgency_score': 0.5  # Базовый уровень
        }
        
        # Извлекаем числовые данные
        numbers = self._extract_numbers(text)
        
        # Пытаемся определить цену (обычно самое большое число с запятыми)
        price = self._guess_price(numbers, text)
        if price:
            gift_data['price'] = price
        
        # Извлекаем эмодзи
        emoji = self._extract_emoji(text)
        if emoji:
            gift_data['emoji'] = emoji
        
        # Если найдены проценты, это может быть доступность
        availability = self._extract_availability(text)
        if availability:
            gift_data.update(availability)
        
        # Пересчитываем urgency на основе найденных данных
        gift_data['urgency_score'] = self._calculate_urgency(gift_data)
        
        # Добавляем краткое описание (первые 100 символов)
        gift_data['description'] = text[:100] + '...' if len(text) > 100 else text
        
        logger.info(f"Detected gift: {gift_data}")
        return gift_data
    
    def _generate_gift_id(self, text: str) -> str:
        """Генерирует уникальный ID на основе текста и времени"""
        # Ищем длинные числа в тексте (возможные ID)
        long_numbers = re.findall(r'\b(\d{10,20})\b', text)
        if long_numbers:
            return long_numbers[0]
        
        # Если нет длинных чисел, генерируем ID из хэша
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        text_hash = hashlib.md5(text.encode()).hexdigest()[:6]
        return f"{timestamp}{text_hash}"
    
    def _extract_numbers(self, text: str) -> List[str]:
        """Извлекает все числа из текста"""
        numbers = []
        for pattern in self.number_patterns:
            matches = re.findall(pattern, text)
            numbers.extend(matches)
        return numbers
    
    def _guess_price(self, numbers: List[str], text: str) -> Optional[str]:
        """Пытается определить цену среди найденных чисел"""
        # Ищем числа рядом со звездочками или словами о цене
        price_indicators = ['⭐', '🌟', 'price', 'цена', 'стоимость', 'cost', '$', '₽']
        
        for indicator in price_indicators:
            # Ищем число перед или после индикатора
            pattern = rf'(\d+(?:,\d+)*)\s*{re.escape(indicator)}|{re.escape(indicator)}\s*(\d+(?:,\d+)*)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) or match.group(2)
        
        # Если не нашли с индикаторами, берем самое большое число с запятыми
        numbers_with_commas = [n for n in numbers if ',' in n]
        if numbers_with_commas:
            return max(numbers_with_commas, key=lambda x: int(x.replace(',', '')))
        
        return None
    
    def _extract_availability(self, text: str) -> Optional[Dict]:
        """Извлекает информацию о доступности"""
        result = {}
        
        # Ищем проценты
        percent_match = re.search(r'(\d+)\s*%', text)
        if percent_match:
            percent = int(percent_match.group(1))
            result['available_percent'] = percent
            
            # Если 0%, значит распродан
            if percent == 0:
                result['is_sold_out'] = True
        
        # Ищем дроби типа 100/1000
        fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
        if fraction_match:
            current = int(fraction_match.group(1))
            total = int(fraction_match.group(2))
            result['available'] = total - current
            result['total'] = total
            if total > 0:
                result['available_percent'] = int((result['available'] / total) * 100)
        
        return result if result else None
    
    def _is_limited_gift(self, text_lower: str) -> bool:
        """Определяет, является ли подарок лимитированным"""
        return any(keyword in text_lower for keyword in self.limited_keywords)
    
    def _is_sold_out(self, text_lower: str) -> bool:
        """Определяет, распродан ли подарок"""
        sold_out_keywords = [
            'sold out', 'распродан', 'закончился', 'нет в наличии',
            'недоступен', 'unavailable', '0%', 'ended'
        ]
        return any(keyword in text_lower for keyword in sold_out_keywords)
    
    def _extract_emoji(self, text: str) -> Optional[str]:
        """Извлекает подходящий эмодзи"""
        gift_emojis = ['🎁', '🎀', '💎', '🎯', '🌟', '⭐', '🔥', '💰', '🏆']
        
        for emoji in gift_emojis:
            if emoji in text:
                return emoji
        
        # Если нет специфичных эмодзи, возвращаем стандартный
        return '🎁'
    
    def _calculate_urgency(self, gift_data: Dict) -> float:
        """Рассчитывает срочность (0-1)"""
        score = 0.3  # Базовый уровень
        
        # Распродан = нет срочности
        if gift_data.get('is_sold_out'):
            return 0.0
        
        # Лимитированный = выше срочность
        if gift_data.get('is_limited'):
            score += 0.3
        
        # Низкая доступность = выше срочность
        available_percent = gift_data.get('available_percent')
        if available_percent is not None:
            if available_percent < 10:
                score += 0.4
            elif available_percent < 25:
                score += 0.3
            elif available_percent < 50:
                score += 0.2
        
        # Ограничиваем максимум
        return min(score, 1.0)
    
    def is_duplicate(self, gift_id: str, recent_gifts: List[str], 
                     time_window: int = 300) -> bool:
        """Проверка на дубликат"""
        return gift_id in recent_gifts
    
    def format_notification_text(self, gift_data: Dict) -> str:
        """Форматирует текст уведомления"""
        parts = []
        
        # Заголовок
        if gift_data.get('is_limited'):
            parts.append("🔥 ЛИМИТИРОВАННЫЙ ПОДАРОК! 🔥")
        else:
            parts.append("🎁 Новый подарок!")
        
        # Цена
        if gift_data.get('price'):
            parts.append(f"💎 Цена: {gift_data['price']} ⭐️")
        
        # Доступность
        if gift_data.get('available_percent') is not None:
            parts.append(f"📊 Доступно: {gift_data['available_percent']}%")
        
        # Описание
        if gift_data.get('description'):
            parts.append(f"\n{gift_data['description']}")
        
    def _extract_marketplaces(self, text: str) -> List[Dict]:
        """Извлекает ссылки на маркетплейсы"""
        marketplaces = []
        
        # Паттерн для ссылок типа: Getgems (https://t.me/...)
        pattern = r'(\w+)\s*\((https://t\.me/[\w/\?=]+)\)'
        matches = re.findall(pattern, text)
        
        for name, url in matches:
            marketplaces.append({
                'name': name,
                'url': url
            })
        
        # Также ищем прямые ссылки
        direct_links = re.findall(r'https://t\.me/[\w/\?=]+', text)
        for link in direct_links:
            if not any(m['url'] == link for m in marketplaces):
                marketplaces.append({
                    'name': 'Telegram',
                    'url': link
                })
        
        return marketplaces
    
    def extract_gift_name(self, text: str) -> Optional[str]:
        """Пытается извлечь название подарка"""
        # Ищем текст после "gift" или "подарок"
        patterns = [
            r'(?:gift|подарок)\s+[«"]([^»"]+)[»"]',
            r'(?:gift|подарок):\s*([^\n.!]+)',
            r'(?:new|новый)\s+([^\s]+)\s+(?:gift|подарок)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None