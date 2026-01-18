#!/bin/bash
# Frepi Agent - GCP VM Setup Script
# Run this script on a fresh Ubuntu 22.04 VM

set -e

echo "=========================================="
echo "  Frepi Agent - GCP Setup"
echo "=========================================="

# Update system
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3.11
echo "🐍 Installing Python 3.11..."
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

# Install pip
echo "📦 Installing pip..."
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Create app directory
echo "📁 Creating app directory..."
sudo mkdir -p /opt/frepi-agent
sudo chown $USER:$USER /opt/frepi-agent

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3.11 -m venv /opt/frepi-agent/venv
source /opt/frepi-agent/venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install anthropic python-telegram-bot supabase openai httpx python-dotenv click rich

# Copy application files (assumes files are in current directory)
echo "📋 Copying application files..."
cp -r frepi_agent /opt/frepi-agent/
cp -r scripts /opt/frepi-agent/ 2>/dev/null || true

# Create .env file placeholder
echo "📝 Creating .env placeholder..."
if [ ! -f /opt/frepi-agent/.env ]; then
    cat > /opt/frepi-agent/.env << 'EOF'
# Frepi Agent Configuration
# Fill in your values below

OPENAI_API_KEY=your-openai-key-here
SUPABASE_URL=your-supabase-url-here
SUPABASE_KEY=your-supabase-key-here
TELEGRAM_BOT_TOKEN=your-telegram-token-here

CHAT_MODEL=gpt-4o
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF
    echo "⚠️  Please edit /opt/frepi-agent/.env with your credentials!"
fi

# Install systemd service
echo "🔧 Installing systemd service..."
sudo cp deploy/frepi-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable frepi-agent

echo ""
echo "=========================================="
echo "  ✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit /opt/frepi-agent/.env with your credentials"
echo "2. Start the service: sudo systemctl start frepi-agent"
echo "3. Check status: sudo systemctl status frepi-agent"
echo "4. View logs: sudo journalctl -u frepi-agent -f"
echo ""
