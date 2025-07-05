#!/usr/bin/env python3
"""
Database Docker Adapter - решение для Windows
Выполняет SQL команды через docker exec
"""

import asyncio
import subprocess
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class DockerPostgresAdapter:
    """Адаптер для работы с PostgreSQL через Docker на Windows"""
    
    def __init__(self):
        self.container_name = "tgm_postgres"
        self.user = "tgm_user"
        self.database = "tgm_db"
        
    async def execute_sql(self, query: str, params: List[Any] = None) -> List[Dict]:
        """Выполняет SQL запрос через docker exec"""
        # Экранируем параметры
        if params:
            # Простая замена параметров (для демонстрации)
            for i, param in enumerate(params):
                if isinstance(param, str):
                    param = param.replace("'", "''")
                    query = query.replace(f"%s", f"'{param}'", 1)
                elif isinstance(param, (list, dict)):
                    param = json.dumps(param).replace("'", "''")
                    query = query.replace(f"%s", f"'{param}'", 1)
                elif param is None:
                    query = query.replace(f"%s", "NULL", 1)
                else:
                    query = query.replace(f"%s", str(param), 1)
        
        # Формируем команду
        cmd = [
            "docker", "exec", "-i", self.container_name,
            "psql", "-U", self.user, "-d", self.database,
            "-t", "-A", "-F", "|",  # Табличный формат с разделителем |
            "-c", query
        ]
        
        try:
            # Выполняем команду
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                logger.error(f"SQL Error: {result.stderr}")
                raise Exception(f"SQL Error: {result.stderr}")
            
            # Парсим результат
            output = result.stdout.strip()
            
            # Для простых запросов типа SELECT 1
            if "SELECT 1" in query.upper():
                return [{"result": output}] if output else []
            
            lines = output.split('\n') if output else []
            rows = []
            
            if lines:
                for line in lines:
                    if line:
                        # Если есть разделитель |, парсим как таблицу
                        if '|' in line:
                            values = line.split('|')
                            rows.append({f"col_{i}": v.strip() for i, v in enumerate(values)})
                        else:
                            # Иначе возвращаем как одно значение
                            rows.append({"result": line})
            
            return rows
            
        except Exception as e:
            logger.error(f"Docker exec error: {e}")
            raise

    async def execute_query(self, query: str, params: List[Any] = None) -> List[Dict]:
        """Execute a SELECT query and return results as list of dicts"""
        if params:
            # Простая замена параметров для PostgreSQL
            for i, param in enumerate(params):
                query = query.replace(f"%s", f"'{param}'", 1)
        
        # Добавляем вывод в формате JSON для правильного парсинга
        wrapped_query = f"""
        SELECT json_agg(row_to_json(t)) 
        FROM ({query}) t
        """
        
        cmd = [
            "docker", "exec", "-i", self.container_name,
            "psql", "-U", self.user, "-d", self.database,
            "-t", "-A", "-c", wrapped_query
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                logger.error(f"Query Error: {result.stderr}")
                return []
                
            if result.stdout.strip() and result.stdout.strip() != 'null':
                import json
                data = json.loads(result.stdout.strip())
                return data if data else []
            return []
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return []

    async def _run_command(self, cmd: List[str]) -> Any:
        """Helper method to run command (for compatibility)"""
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        return result


class Database:
    """Async database operations handler using Docker adapter"""
    
    def __init__(self, connection_url: str = None):
        self.adapter = DockerPostgresAdapter()
        self.initialized = False
        # Добавляем атрибут pool для совместимости
        self.pool = None
    
    async def initialize(self):
        """Initialize database connection"""
        try:
            # Тестируем подключение
            result = await self.adapter.execute_sql("SELECT 1")
            if result and len(result) > 0:
                logger.info("Database connection via Docker successful")
                self.initialized = True
                # Устанавливаем pool для совместимости с кодом
                self.pool = True
            else:
                raise Exception("Test query failed")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connection"""
        # Ничего не нужно закрывать
        pass
    
    # Добавим метод execute_query для совместимости с API
    async def execute_query(self, query: str, params: List[Any] = None) -> List[Dict]:
        """Execute query - delegate to adapter"""
        return await self.adapter.execute_query(query, params)
    
    # Channel operations
    async def get_active_channels(self) -> List[Dict]:
        """Get all active channels"""
        if not self.initialized:
            return []
            
        try:
            query = """
                SELECT id::text as id, 
                       telegram_id::text as telegram_id, 
                       username, 
                       title, 
                       COALESCE(array_to_string(keywords, ','), '') as keywords
                FROM channels 
                WHERE is_active = TRUE
            """
            result = await self.adapter.execute_sql(query)
            
            # Отладочный вывод
            logger.debug(f"Raw result from get_active_channels: {result}")
            
            channels = []
            for row in result:
                channel = {}
                # Парсим результат построчно
                if 'result' in row:
                    # Если результат в одной строке, разбираем по разделителю
                    parts = row['result'].split('|')
                    if len(parts) >= 5:
                        channel = {
                            'id': parts[0],
                            'telegram_id': int(parts[1]),
                            'username': parts[2],
                            'title': parts[3],
                            'keywords': parts[4].split(',') if parts[4] else []
                        }
                else:
                    # Если результат уже разобран
                    channel = {
                        'id': row.get('col_0', row.get('id', '')),
                        'telegram_id': int(row.get('col_1', row.get('telegram_id', 0))),
                        'username': row.get('col_2', row.get('username', '')),
                        'title': row.get('col_3', row.get('title', '')),
                        'keywords': []
                    }
                    
                    # Обработка keywords
                    keywords_str = row.get('col_4', row.get('keywords', ''))
                    if keywords_str and keywords_str != '{}':
                        channel['keywords'] = keywords_str.strip('{}').split(',')
                
                if channel.get('telegram_id'):
                    channels.append(channel)
                    
            return channels
        except Exception as e:
            logger.error(f"Error getting active channels: {e}")
            return []
    
    async def add_channel(self, channel_id: int, username: str,
                         title: str, keywords: List[str] = None):
        """Add new channel"""
        if not self.initialized:
            return
            
        try:
            keywords_str = '{' + ','.join(keywords or []) + '}'
            query = f"""
                INSERT INTO channels (telegram_id, username, title, keywords)
                VALUES ({channel_id}, '{username}', '{title}', '{keywords_str}')
                ON CONFLICT (telegram_id) DO UPDATE
                SET username = EXCLUDED.username,
                    title = EXCLUDED.title,
                    keywords = EXCLUDED.keywords,
                    is_active = TRUE
            """
            await self.adapter.execute_sql(query)
            logger.info(f"Channel {username} added to database")
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
    
    async def save_notification(self, channel_id: int, channel_username: str,
                              message_text: str, gift_data: dict,
                              message_link: str) -> Optional[int]:
        """Save notification to database"""
        if not self.initialized:
            return None
            
        try:
            # Получаем UUID канала
            query = f"SELECT id::text as id FROM channels WHERE telegram_id = {channel_id}"
            result = await self.adapter.execute_sql(query)
            
            channel_uuid = None
            if result and len(result) > 0:
                if 'result' in result[0]:
                    channel_uuid = result[0]['result']
                elif 'id' in result[0]:
                    channel_uuid = result[0]['id']
                elif 'col_0' in result[0]:
                    channel_uuid = result[0]['col_0']
            
            if not channel_uuid:
                # Создаем канал
                query = f"""
                    INSERT INTO channels (telegram_id, username, title)
                    VALUES ({channel_id}, '{channel_username}', '{channel_username}')
                    RETURNING id::text
                """
                result = await self.adapter.execute_sql(query)
                if result and len(result) > 0:
                    if 'result' in result[0]:
                        channel_uuid = result[0]['result']
                    elif 'id' in result[0]:
                        channel_uuid = result[0]['id']
                    elif 'col_0' in result[0]:
                        channel_uuid = result[0]['col_0']
            
            if not channel_uuid:
                logger.error("Failed to get channel UUID")
                return None
            
            # Сохраняем уведомление
            gift_data_json = json.dumps(gift_data).replace("'", "''")
            message_text_escaped = message_text[:500].replace("'", "''")  # Ограничиваем длину
            
            query = f"""
                INSERT INTO notifications (
                    channel_id, message_text, gift_id, 
                    gift_data, message_link
                )
                VALUES (
                    '{channel_uuid}'::uuid, 
                    '{message_text_escaped}', 
                    '{gift_data.get('id', '')}',
                    '{gift_data_json}'::jsonb, 
                    '{message_link}'
                )
                RETURNING id::text
            """
            result = await self.adapter.execute_sql(query)
            
            notification_id = None
            if result and len(result) > 0:
                if 'result' in result[0]:
                    notification_id = result[0]['result']
                elif 'id' in result[0]:
                    notification_id = result[0]['id']
                elif 'col_0' in result[0]:
                    notification_id = result[0]['col_0']
                
                # Обновляем статистику канала
                update_query = f"""
                    UPDATE channels 
                    SET total_gifts_detected = total_gifts_detected + 1,
                        last_checked_at = CURRENT_TIMESTAMP
                    WHERE id = '{channel_uuid}'::uuid
                """
                await self.adapter.execute_sql(update_query)
                
                logger.info(f"Notification saved with ID: {notification_id}")
                return int(notification_id) if notification_id and notification_id.isdigit() else 1
            
            return None
                
        except Exception as e:
            logger.error(f"Error saving notification: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    # Заглушки для остальных методов
    async def get_active_users_for_channel(self, channel_username: str) -> List[Dict]:
        """Get all active users subscribed to a channel"""
        return []
    
    async def get_user_fcm_tokens(self, user_id: str) -> List[str]:
        """Get user's active FCM tokens"""
        return []
    
    async def increment_channel_stats(self, channel_username: str, gift_count: int):
        """Update channel statistics"""
        if not self.initialized:
            return
            
        try:
            query = f"""
                UPDATE channels 
                SET total_gifts_detected = total_gifts_detected + {gift_count},
                    last_checked_at = CURRENT_TIMESTAMP
                WHERE username = '{channel_username}'
            """
            await self.adapter.execute_sql(query)
        except Exception as e:
            logger.error(f"Error updating channel stats: {e}")
    
    async def add_gift_price_history(self, gift_id: str, price: str, timestamp: datetime):
        """Add gift price history record"""
        if not self.initialized:
            return
            
        try:
            query = f"""
                INSERT INTO gift_price_history (gift_id, price, detected_at)
                VALUES ('{gift_id}', '{price}', '{timestamp.isoformat()}')
            """
            await self.adapter.execute_sql(query)
        except Exception as e:
            logger.error(f"Error adding price history: {e}")
    
    async def log_notification_delivery(self, notification_id: int, user_id: str, delivered: bool):
        """Log notification delivery status"""
        # Заглушка - у нас нет пользователей
        pass