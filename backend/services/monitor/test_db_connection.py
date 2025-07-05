#!/usr/bin/env python3
"""
Test database connection with detailed error reporting
"""

import psycopg2
import os
from dotenv import load_dotenv

# Загружаем .env
env_path = r'C:\telegram-gift-monitor\.env'
load_dotenv(env_path)

DATABASE_URL = os.getenv('DATABASE_URL')
print(f"DATABASE_URL: {DATABASE_URL}")

# Пробуем разные способы подключения
connections_to_try = [
    {
        "name": "Using DATABASE_URL",
        "params": DATABASE_URL
    },
    {
        "name": "Direct parameters with localhost",
        "params": {
            "host": "localhost",
            "port": 5432,
            "database": "tgm_db",
            "user": "tgm_user",
            "password": "tgm_secure_password_change_this"
        }
    },
    {
        "name": "Direct parameters with 127.0.0.1",
        "params": {
            "host": "127.0.0.1",
            "port": 5432,
            "database": "tgm_db",
            "user": "tgm_user",
            "password": "tgm_secure_password_change_this"
        }
    },
    {
        "name": "Direct parameters with host.docker.internal",
        "params": {
            "host": "host.docker.internal",
            "port": 5432,
            "database": "tgm_db",
            "user": "tgm_user",
            "password": "tgm_secure_password_change_this"
        }
    }
]

for conn_info in connections_to_try:
    print(f"\n{'='*60}")
    print(f"Trying: {conn_info['name']}")
    print(f"{'='*60}")
    
    try:
        if isinstance(conn_info['params'], str):
            conn = psycopg2.connect(conn_info['params'])
        else:
            conn = psycopg2.connect(**conn_info['params'])
        
        print("✅ SUCCESS! Connected to database")
        
        # Тест запроса
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()
        print(f"PostgreSQL version: {version[0]}")
        
        cur.close()
        conn.close()
        
        print(f"\n🎉 Working connection found: {conn_info['name']}")
        break
        
    except psycopg2.OperationalError as e:
        print(f"❌ psycopg2.OperationalError: {e}")
        print(f"   Details: {str(e)}")
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")

print("\n" + "="*60)

# Проверим также, слушает ли PostgreSQL порт
import subprocess
try:
    result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
    postgres_lines = [line for line in result.stdout.split('\n') if ':5432' in line]
    if postgres_lines:
        print("\nPostgreSQL listening on:")
        for line in postgres_lines:
            print(f"  {line.strip()}")
    else:
        print("\n⚠️ PostgreSQL не найден на порту 5432")
except:
    pass