#!/bin/bash
echo "🧬 RepurposeAI — Drug Repurposing Intelligence Platform"
echo "======================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

# Check for API key
if grep -q "your_api_key_here" .env; then
    echo "⚠️  WARNING: No Anthropic API key set in .env file"
    echo "   The app will run in demo mode (real data, mock AI synthesis)"
    echo "   Get a free key at: https://console.anthropic.com"
    echo ""
fi

echo "🚀 Starting server at http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

# Load env and run
cd backend
export $(grep -v '^#' ../.env | xargs) 2>/dev/null
python3 app.py
