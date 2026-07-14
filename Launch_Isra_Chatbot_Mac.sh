#!/bin/bash

echo "==================================================="
echo "            ISRA CHATBOT LAUNCHER (MAC)"
echo "==================================================="
echo ""
echo "Starting the AI Server via Docker..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "[INFO] Docker is not running. Starting Docker Desktop in the background..."
    # Programmatically disable the Docker Dashboard popup in settings
    python3 -c "import json, os; p=os.path.expanduser('~/Library/Group Containers/group.com.docker/settings.json'); data=json.load(open(p)) if os.path.exists(p) else {}; data['openUIOnStartup']=False; json.dump(data, open(p, 'w'))" 2>/dev/null || true
    open -j -g -a Docker
    echo "[INFO] Waiting for Docker to start (this may take a minute)..."
    while ! docker info >/dev/null 2>&1; do
        sleep 2
    done
    
    # Forcefully hide the Docker GUI window that pops up
    osascript -e 'tell application "System Events" to set visible of process "Docker" to false' 2>/dev/null || true
    
    echo "[SUCCESS] Docker is now running!"
    echo ""
fi

# Check if the container already exists
if docker ps -a --format '{{.Names}}' | grep -Eq "^isra_bot$"; then
    echo "[INFO] Resuming existing Chatbot server..."
    docker start isra_bot >/dev/null
else
    echo "[INFO] First time setup: Launching Chatbot..."
    docker run -p 8000:8000 -d --name isra_bot -e EMBEDDING_PROVIDER=ollama -v isra_data:/app/backend/data isra-chatbot:latest >/dev/null
fi

echo ""
echo "[INFO] Waiting for the AI brain to initialize..."
sleep 5

echo ""
echo "[SUCCESS] Opening Isra Chatbot in your default web browser!"
open "http://localhost:8000"

echo ""
echo "You can safely close this terminal window. The server will keep running in Docker!"
sleep 3
