#!/usr/bin/env python3
"""Test docker database connection"""

import subprocess

# Тест 1: Простой SELECT
print("Test 1: Simple SELECT")
cmd = ["docker", "exec", "-i", "tgm_postgres", "psql", "-U", "tgm_user", "-d", "tgm_db", "-t", "-A", "-c", "SELECT 1"]
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"Return code: {result.returncode}")
print(f"Stdout: '{result.stdout}'")
print(f"Stderr: '{result.stderr}'")
print(f"Result stripped: '{result.stdout.strip()}'")
print()

# Тест 2: SELECT с алиасом
print("Test 2: SELECT with alias")
cmd = ["docker", "exec", "-i", "tgm_postgres", "psql", "-U", "tgm_user", "-d", "tgm_db", "-t", "-A", "-c", "SELECT 1 as test"]
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"Return code: {result.returncode}")
print(f"Stdout: '{result.stdout}'")
print(f"Result stripped: '{result.stdout.strip()}'")
print()

# Тест 3: Проверка таблиц
print("Test 3: Check tables")
cmd = ["docker", "exec", "-i", "tgm_postgres", "psql", "-U", "tgm_user", "-d", "tgm_db", "-t", "-A", "-c", "SELECT tablename FROM pg_tables WHERE schemaname='public' LIMIT 5"]
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"Return code: {result.returncode}")
print(f"Tables found:")
for line in result.stdout.strip().split('\n'):
    if line:
        print(f"  - {line}")