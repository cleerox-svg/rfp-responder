#!/bin/bash
# NaughtRFP — one-command setup for Mac/Linux
# Usage: bash setup.sh

set -e

echo ""
echo "  NaughtRFP Setup"
echo "  ─────────────────────────────────"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv venv
fi

# Activate and install
echo "  Installing dependencies..."
source venv/bin/activate
pip install --quiet flask anthropic openpyxl python-docx pdfplumber

# Copy .env if not present
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo ""
  echo "  ⚠  .env created from .env.example"
  echo "     Edit .env and add your LITELLM_API_KEY before starting."
  echo ""
fi

echo "  ✓ Setup complete."
echo ""
echo "  To start the app:"
echo "    source venv/bin/activate"
echo "    python app.py"
echo ""
echo "  Then open http://localhost:5000 in your browser."
echo ""
