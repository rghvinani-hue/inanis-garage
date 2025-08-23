#!/bin/bash

# 🔧 Inanis Garage - Quick Start Script

echo "🔧 Inanis Garage Management System - Quick Start"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Create necessary directories
print_info "Creating directories for Inanis Garage..."
mkdir -p data temp_uploads logs static/css templates

print_status "Directories created"

# Check dependencies
print_info "Checking system requirements..."

# Check if Docker is available
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    print_info "Docker found - using containerized deployment"

    print_info "Building Inanis Garage container..."
    if docker-compose build; then
        print_status "Container built successfully"
    else
        print_error "Failed to build container"
        exit 1
    fi

    print_info "Starting Inanis Garage..."
    if docker-compose up -d; then
        print_status "Inanis Garage started with Docker!"
        DEPLOYMENT="docker"
    else
        print_error "Failed to start with Docker, trying Python..."
        DEPLOYMENT="python"
    fi

elif command -v python3 &> /dev/null; then
    print_info "Python 3 found - using direct deployment"

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv venv
    fi

    print_info "Activating virtual environment..."
    source venv/bin/activate

    print_info "Installing dependencies..."
    if pip install -r requirements.txt; then
        print_status "Dependencies installed"
    else
        print_warning "Some dependencies failed - app may work with basic functionality"
    fi

    print_info "Starting Inanis Garage..."
    python3 app.py &
    DEPLOYMENT="python"
    print_status "Inanis Garage started with Python!"

else
    print_error "Neither Docker nor Python 3 found!"
    print_error "Please install either:"
    print_error "  - Docker and Docker Compose"
    print_error "  - Python 3.8 or higher"
    exit 1
fi

# Wait for service to start
print_info "Waiting for Inanis Garage to start..."
sleep 5

# Check if the service is running
if curl -f http://localhost:5000 > /dev/null 2>&1; then
    print_status "Inanis Garage is running successfully!"
else
    print_warning "Service might still be starting..."
fi

echo ""
echo "🎉 Inanis Garage is ready!"
echo "=============================================="
echo ""
print_status "🌐 Access Your Garage System:"
echo "   Local:    http://localhost:5000"
echo "   Network:  http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'your-ip'):5000"
echo ""
print_status "🔑 Default Login Credentials:"
echo "   Username: admin"
echo "   Password: adminpass"
echo "   ⚠️  CHANGE PASSWORD IMMEDIATELY AFTER FIRST LOGIN!"
echo ""
print_status "🔧 Management Commands:"
if [ "$DEPLOYMENT" = "docker" ]; then
    echo "   View logs:     docker-compose logs -f inanis-garage"
    echo "   Stop service:  docker-compose down"
    echo "   Restart:       docker-compose restart inanis-garage"
    echo "   Update:        docker-compose up -d --build"
else
    echo "   View logs:     tail -f logs/flask_app.log"
    echo "   Stop service:  pkill -f app.py"
    echo "   Restart:       python3 app.py"
fi
echo ""
print_status "📁 Important Directories:"
echo "   Garage data:      ./data/"
echo "   Uploaded files:   ./temp_uploads/"
echo "   System logs:      ./logs/"
echo ""
print_status "☁️  Google Integration (Optional):"
echo "   📋 For Google Drive & Calendar features:"
echo "   1. Place credentials.json in this directory"
echo "   2. Restart Inanis Garage"
echo "   3. See GOOGLE_SETUP.md for instructions"
echo ""
print_status "🔧 You're all set! Welcome to Inanis Garage!"

# Check for Google credentials
if [ -f "credentials.json" ]; then
    print_status "Google credentials found - Cloud features enabled!"
else
    print_info "No Google credentials - App works great without them too!"
fi

echo ""
print_info "📖 For detailed instructions, see README.md"
print_info "🐛 If you encounter issues, check the logs mentioned above"

echo ""
echo "🔧 Welcome to Inanis Garage - Professional Fleet Management!"
