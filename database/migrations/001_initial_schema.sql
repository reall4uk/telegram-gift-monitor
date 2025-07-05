-- Telegram Gift Monitor Database Schema
-- Version: 1.0.0

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(255),
    has_valid_license BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_banned BOOLEAN DEFAULT FALSE,
    ban_reason VARCHAR(500),
    risk_score DECIMAL(3, 2) DEFAULT 0.00 CHECK (risk_score >= 0 AND risk_score <= 1)
);

-- Indexes for users
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_has_valid_license ON users(has_valid_license);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Licenses table
CREATE TABLE licenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    license_key VARCHAR(255) UNIQUE NOT NULL,
    license_type VARCHAR(50) NOT NULL CHECK (license_type IN ('trial', 'basic', 'pro', 'lifetime')),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoke_reason VARCHAR(500),
    max_channels INTEGER NOT NULL DEFAULT 1,
    max_devices INTEGER NOT NULL DEFAULT 1,
    duration_days INTEGER NOT NULL,
    activation_device_id VARCHAR(255),
    CONSTRAINT valid_expiration CHECK (expires_at IS NULL OR expires_at > activated_at)
);

-- Indexes for licenses
CREATE INDEX idx_licenses_user_id ON licenses(user_id);
CREATE INDEX idx_licenses_license_key ON licenses(license_key);
CREATE INDEX idx_licenses_expires_at ON licenses(expires_at);
CREATE INDEX idx_licenses_activated_at ON licenses(activated_at);

-- User devices table
CREATE TABLE user_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(255) NOT NULL,
    device_type VARCHAR(50) NOT NULL CHECK (device_type IN ('android', 'ios', 'web')),
    device_name VARCHAR(255),
    fcm_token TEXT,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    app_version VARCHAR(50),
    os_version VARCHAR(50),
    UNIQUE(user_id, device_id)
);

-- Indexes for user_devices
CREATE INDEX idx_user_devices_user_id ON user_devices(user_id);
CREATE INDEX idx_user_devices_fcm_token ON user_devices(fcm_token);
CREATE INDEX idx_user_devices_last_seen ON user_devices(last_seen_at);

-- Channels table
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    keywords TEXT[] DEFAULT '{}',
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_checked_at TIMESTAMP WITH TIME ZONE,
    total_gifts_detected INTEGER DEFAULT 0,
    subscriber_count INTEGER DEFAULT 0
);

-- Indexes for channels
CREATE INDEX idx_channels_username ON channels(username);
CREATE INDEX idx_channels_is_active ON channels(is_active);
CREATE INDEX idx_channels_keywords ON channels USING GIN(keywords);

-- User channel subscriptions
CREATE TABLE user_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    subscribed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_muted BOOLEAN DEFAULT FALSE,
    muted_until TIMESTAMP WITH TIME ZONE,
    notification_sound VARCHAR(100) DEFAULT 'default',
    priority_override VARCHAR(50),
    UNIQUE(user_id, channel_id)
);

-- Indexes for subscriptions
CREATE INDEX idx_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX idx_subscriptions_channel_id ON user_subscriptions(channel_id);
CREATE INDEX idx_subscriptions_is_muted ON user_subscriptions(is_muted);

-- Notifications table
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    message_text TEXT,
    gift_id VARCHAR(255),
    gift_data JSONB,
    message_link TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_recipients INTEGER DEFAULT 0,
    successful_deliveries INTEGER DEFAULT 0,
    failed_deliveries INTEGER DEFAULT 0
);

-- Indexes for notifications
CREATE INDEX idx_notifications_channel_id ON notifications(channel_id);
CREATE INDEX idx_notifications_gift_id ON notifications(gift_id);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);
CREATE INDEX idx_notifications_gift_data ON notifications USING GIN(gift_data);

-- Notification delivery log
CREATE TABLE notification_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES user_devices(id) ON DELETE CASCADE,
    delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    failure_reason VARCHAR(500),
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for deliveries
CREATE INDEX idx_deliveries_notification_id ON notification_deliveries(notification_id);
CREATE INDEX idx_deliveries_user_id ON notification_deliveries(user_id);
CREATE INDEX idx_deliveries_delivered ON notification_deliveries(delivered);

-- User settings table
CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    sound_enabled BOOLEAN DEFAULT TRUE,
    vibration_enabled BOOLEAN DEFAULT TRUE,
    led_enabled BOOLEAN DEFAULT TRUE,
    quiet_hours_enabled BOOLEAN DEFAULT FALSE,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    notification_sound VARCHAR(100) DEFAULT 'alarm_loud',
    repeat_count INTEGER DEFAULT 3 CHECK (repeat_count >= 1 AND repeat_count <= 10),
    auto_dismiss_seconds INTEGER DEFAULT 0,
    language_code VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Gift price history (for analytics)
CREATE TABLE gift_price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gift_id VARCHAR(255) NOT NULL,
    price VARCHAR(50),
    currency VARCHAR(10) DEFAULT 'stars',
    availability_percent INTEGER,
    total_supply INTEGER,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for price history
CREATE INDEX idx_price_history_gift_id ON gift_price_history(gift_id);
CREATE INDEX idx_price_history_detected_at ON gift_price_history(detected_at);

-- API keys table (for future use)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    permissions JSONB DEFAULT '{}',
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Security audit log
CREATE TABLE security_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for audit log
CREATE INDEX idx_audit_log_user_id ON security_audit_log(user_id);
CREATE INDEX idx_audit_log_action ON security_audit_log(action);
CREATE INDEX idx_audit_log_created_at ON security_audit_log(created_at);

-- System statistics table
CREATE TABLE system_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stat_date DATE NOT NULL,
    total_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    total_notifications INTEGER DEFAULT 0,
    successful_notifications INTEGER DEFAULT 0,
    new_licenses INTEGER DEFAULT 0,
    revenue_amount DECIMAL(10, 2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stat_date)
);

-- Functions and triggers

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to check license validity
CREATE OR REPLACE FUNCTION is_license_valid(license_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    license_record RECORD;
BEGIN
    SELECT * INTO license_record FROM licenses WHERE id = license_id;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    IF license_record.revoked_at IS NOT NULL THEN
        RETURN FALSE;
    END IF;
    
    IF license_record.activated_at IS NULL THEN
        RETURN FALSE;
    END IF;
    
    IF license_record.expires_at < CURRENT_TIMESTAMP THEN
        RETURN FALSE;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to update channel subscriber count
CREATE OR REPLACE FUNCTION update_channel_subscriber_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE channels 
        SET subscriber_count = subscriber_count + 1 
        WHERE id = NEW.channel_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE channels 
        SET subscriber_count = subscriber_count - 1 
        WHERE id = OLD.channel_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for subscriber count
CREATE TRIGGER update_channel_subscribers
AFTER INSERT OR DELETE ON user_subscriptions
FOR EACH ROW EXECUTE FUNCTION update_channel_subscriber_count();

-- Initial data
INSERT INTO channels (telegram_id, username, title, description, keywords) VALUES
(-1001234567890, '@example_gifts', 'Example Gift Channel', 'Test channel for development', ARRAY['gift', 'new', 'limited']),
(-1009876543210, '@rare_drops', 'Rare Drops Alert', 'Premium gifts notification', ARRAY['rare', 'подарок', 'редкий']);

-- Create indexes for performance
CREATE INDEX idx_notifications_created_at_desc ON notifications(created_at DESC);
CREATE INDEX idx_user_devices_active ON user_devices(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_licenses_valid ON licenses(user_id, expires_at) WHERE revoked_at IS NULL;

-- Views for common queries

-- Active users with valid licenses
CREATE VIEW active_licensed_users AS
SELECT 
    u.id,
    u.telegram_id,
    u.telegram_username,
    l.license_type,
    l.expires_at,
    COUNT(DISTINCT ud.id) as device_count,
    COUNT(DISTINCT us.channel_id) as subscription_count
FROM users u
JOIN licenses l ON u.id = l.user_id
LEFT JOIN user_devices ud ON u.id = ud.user_id AND ud.is_active = TRUE
LEFT JOIN user_subscriptions us ON u.id = us.user_id
WHERE u.has_valid_license = TRUE
    AND u.is_banned = FALSE
    AND l.revoked_at IS NULL
    AND l.expires_at > CURRENT_TIMESTAMP
GROUP BY u.id, u.telegram_id, u.telegram_username, l.license_type, l.expires_at;

-- Grant permissions (adjust for your user)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tgm_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tgm_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO tgm_user;