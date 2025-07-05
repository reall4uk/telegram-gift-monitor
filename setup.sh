#!/bin/bash

# Telegram Gift Monitor - Setup Script
# This script helps you set up the development environment

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Check requirements
check_requirements() {
    print_step "Checking system requirements..."
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python 3 not found. Please install Python 3.9+"
        exit 1
    fi
    
    # Check Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | sed 's/,$//')
        print_success "Docker $DOCKER_VERSION found"
    else
        print_error "Docker not found. Please install Docker"
        exit 1
    fi
    
    # Check Docker Compose
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f3 | sed 's/,$//')
        print_success "Docker Compose $COMPOSE_VERSION found"
    else
        print_warning "Docker Compose not found. Checking for docker compose..."
        if docker compose version &> /dev/null; then
            print_success "Docker Compose (plugin) found"
        else
            print_error "Docker Compose not found. Please install Docker Compose"
            exit 1
        fi
    fi
}

# Create directory structure
create_directories() {
    print_step "Creating directory structure..."
    
    directories=(
        "backend/services/monitor"
        "backend/services/api"
        "backend/services/shared"
        "database/migrations"
        "database/seeds"
        "mobile/lib"
        "scripts"
        "docs"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        print_success "Created $dir"
    done
}

# Create .env file
create_env_file() {
    print_step "Creating .env file..."
    
    if [ -f .env ]; then
        print_warning ".env file already exists. Backing up to .env.backup"
        cp .env .env.backup
    fi
    
    cat > .env << 'EOF'
# Telegram Configuration
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+1234567890

# Database Configuration
DATABASE_URL=postgresql://tgm_user:tgm_secure_password_change_this@localhost:5432/tgm_db
REDIS_URL=redis://:redis_secure_password_change_this@localhost:6379

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
LICENSE_SIGNING_KEY=another-random-string-for-licenses

# Firebase (for push notifications)
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_PRIVATE_KEY=your_private_key
FIREBASE_CLIENT_EMAIL=your_client_email

# Monitoring Configuration
MONITOR_CHANNELS=@example_gifts,@rare_drops
GIFT_KEYWORDS=new limited gift,редкий,подарок

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Admin Configuration
ADMIN_KEY=your-secret-admin-key

# Environment
ENVIRONMENT=development
DEBUG=true
EOF
    
    print_success ".env file created. Please update it with your actual values!"
}

# Setup Python virtual environment
setup_python_env() {
    print_step "Setting up Python virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists"
    else
        python3 -m venv venv
        print_success "Virtual environment created"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    print_step "Installing Python dependencies..."
    pip install -r backend/services/monitor/requirements.txt
    print_success "Python dependencies installed"
}

# Copy service files
copy_service_files() {
    print_step "Copying service files..."
    
    # Copy monitor service files
    cp telegram_monitor.py backend/services/monitor/
    cp gift_detector.py backend/services/monitor/
    print_success "Monitor service files copied"
    
    # Copy API service files
    cp main.py backend/services/api/
    cp auth.py backend/services/api/
    cp licenses.py backend/services/api/
    print_success "API service files copied"
    
    # Copy shared files
    touch backend/services/shared/__init__.py
    touch backend/services/shared/database.py
    touch backend/services/shared/models.py
    touch backend/services/shared/config.py
    touch backend/services/shared/utils.py
    print_success "Shared module files created"
}

# Start services
start_services() {
    print_step "Starting Docker services..."
    
    # Start only database and Redis first
    docker-compose up -d postgres redis
    
    print_step "Waiting for services to be ready..."
    sleep 10
    
    # Check if PostgreSQL is ready
    until docker-compose exec -T postgres pg_isready -U tgm_user -d tgm_db; do
        print_warning "Waiting for PostgreSQL..."
        sleep 2
    done
    print_success "PostgreSQL is ready"
    
    # Check if Redis is ready
    until docker-compose exec -T redis redis-cli ping; do
        print_warning "Waiting for Redis..."
        sleep 2
    done
    print_success "Redis is ready"
}

# Generate first license
generate_license() {
    print_step "Generating test license..."
    
    # Create license generation script
    cat > scripts/generate_license.py << 'EOF'
#!/usr/bin/env python3
import sys
sys.path.append('../backend/services/api')
from licenses import LicenseService

service = LicenseService()
license_data = service.generate_license_key("trial")

print("\n=== Test License Generated ===")
print(f"License Key: {license_data['key']}")
print(f"Type: {license_data['type']}")
print(f"Valid for: 7 days")
print(f"Max Channels: 1")
print("==============================\n")
EOF
    
    chmod +x scripts/generate_license.py
    cd scripts && python3 generate_license.py && cd ..
}

# Display next steps
show_next_steps() {
    echo
    echo -e "${GREEN}✓ Setup completed successfully!${NC}"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Update the .env file with your Telegram API credentials"
    echo "   - Get them from https://my.telegram.org"
    echo
    echo "2. Update Firebase credentials for push notifications"
    echo "   - Create a project at https://console.firebase.google.com"
    echo "   - Download service account key"
    echo
    echo "3. Start all services:"
    echo "   docker-compose up -d"
    echo
    echo "4. Run the API server locally:"
    echo "   cd backend/services/api"
    echo "   python main.py"
    echo
    echo "5. Run the monitor service:"
    echo "   cd backend/services/monitor"
    echo "   python telegram_monitor.py"
    echo
    echo "6. Access services:"
    echo "   - API: http://localhost:8000"
    echo "   - API Docs: http://localhost:8000/docs"
    echo "   - pgAdmin: http://localhost:5050 (if using development profile)"
    echo
    echo -e "${YELLOW}Documentation:${NC}"
    echo "   - API Documentation: docs/API.md"
    echo "   - Setup Guide: docs/SETUP.md"
    echo "   - Security Guide: docs/SECURITY.md"
    echo
}

# Main execution
main() {
    echo -e "${BLUE}Telegram Gift Monitor - Setup Script${NC}"
    echo "====================================="
    echo
    
    check_requirements
    create_directories
    create_env_file
    setup_python_env
    copy_service_files
    start_services
    generate_license
    show_next_steps
}

# Run main function
main