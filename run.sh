#!/bin/bash
# BillBuddy startup script

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv .venv
    echo "Virtual environment created."
fi

# Activate virtual environment
source .venv/bin/activate

# Check if dependencies are installed
if [ ! -f ".venv/installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    touch .venv/installed
    echo "Dependencies installed."
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo "Please create .env file from .env.example and configure your credentials."
    echo "Run: cp .env.example .env"
    exit 1
fi

# Start the bot
echo "Starting BillBuddy..."
python app/main.py
