#!/bin/bash

# Production setup script for Telegram Gift Monitor

echo "Setting up Telegram Gift Monitor for production..."

# Install Python dependencies
cd /opt/telegram-gift-monitor
source venv/bin/activate

# Install monitor dependencies
pip install -r backend/services/monitor/requirements.txt

# Create necessary directories
mkdir -p logs
mkdir -p sessions

# Set permissions
chmod +x backend/services/monitor/telegram_monitor.py
chmod +x backend/services/api/main.py

# Create systemd service for monitor
sudo tee /etc/systemd/system/tgm-monitor.service > /dev/null <<EOF
[Unit]
Description=Telegram Gift Monitor Service
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/telegram-gift-monitor
Environment="PATH=/opt/telegram-gift-monitor/venv/bin"
ExecStart=/opt/telegram-gift-monitor/venv/bin/python backend/services/monitor/telegram_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for API
sudo tee /etc/systemd/system/tgm-api.service > /dev/null <<EOF
[Unit]
Description=Telegram Gift Monitor API
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/telegram-gift-monitor
Environment="PATH=/opt/telegram-gift-monitor/venv/bin"
ExecStart=/opt/telegram-gift-monitor/venv/bin/python backend/services/api/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo "Setup complete! You can now:"
echo "1. Start monitor: sudo systemctl start tgm-monitor"
echo "2. Start API: sudo systemctl start tgm-api"
echo "3. Enable auto-start: sudo systemctl enable tgm-monitor tgm-api"