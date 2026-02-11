#!/bin/bash
# MemAgent Startup Script for Unix/Linux/Mac
# Starts both backend and frontend

echo "Starting MemAgent..."

# Check if backend virtual environment exists
if [ ! -d "backend/.venv" ]; then
    echo "Backend virtual environment not found. Please run setup first."
    exit 1
fi

# Start backend
echo "Starting backend..."
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "MemAgent is running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3002"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop both servers"

# Trap Ctrl+C to kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

# Wait for processes
wait
