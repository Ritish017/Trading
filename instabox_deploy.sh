#!/bin/bash
# =============================================================================
# APEX Quant Lab & J.A.R.V.I.S. Autonomous Bot - InstaBox Cloud Setup Script
# =============================================================================
# Run inside an InstaBox microVM shell (`npx instabox@latest sh`):
#   curl -fsSL https://raw.githubusercontent.com/Ritish017/Trading/main/instabox_deploy.sh | bash
# Or execute directly:
#   chmod +x instabox_deploy.sh && ./instabox_deploy.sh
# =============================================================================

set -e

echo "🚀 [APEX CLOUD] Initializing APEX Quant Lab on InstaBox microVM..."

# Ensure directory
mkdir -p /root/apex-trading
cd /root/apex-trading

# Sync repository
if [ ! -d ".git" ]; then
    echo "📦 Cloning repository..."
    git clone https://github.com/Ritish017/Trading.git . || git init
fi
echo "🔄 Updating codebase..."
git pull origin main || true

# Environment configuration
echo "⚙️ Configuring environment variables..."
cat << 'EOF' > .env
GEMINI_API_KEY=${GEMINI_API_KEY:-""}
UPSTOX_ACCESS_TOKEN=${UPSTOX_ACCESS_TOKEN:-""}
PAPER_TRADING=true
DEFAULT_PAPER_CAPITAL=10000.0
PORT=8001
ENVIRONMENT=production
EOF

# Setup Python venv
echo "🐍 Setting up Python 3 virtual environment..."
python3 -m venv venv || true
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt || pip install fastapi uvicorn httpx pydantic pandas numpy scikit-learn

# Build frontend if Node is present
if command -v npm &> /dev/null; then
    echo "🌐 Building frontend application..."
    cd frontend && npm install --silent && npm run build && cd ..
fi

# Stop existing processes
echo "🛑 Restarting backend services..."
pkill -f "uvicorn backend.app.main:app" || true

# Start FastAPI backend in background
echo "▶️ Launching APEX Quant Lab Autonomous Daemon..."
nohup python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8001 > /root/apex_backend.log 2>&1 &

sleep 3
if pgrep -f "backend.app.main:app" > /dev/null; then
    echo "✅ [APEX CLOUD ONLINE] Backend daemon is running on port 8001!"
    echo "📊 J.A.R.V.I.S. Autonomous Trading Engine is active."
    echo "💰 Initial Paper Trading Capital: ₹10,000.00"
    echo "📜 Live log available at: tail -f /root/apex_backend.log"
else
    echo "❌ Failed to start backend daemon. Check /root/apex_backend.log for errors."
    exit 1
fi
