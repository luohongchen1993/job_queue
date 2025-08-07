#!/bin/bash

echo "=== Testing Job Queue System ==="

echo "1. Adding test jobs..."
./jq add "echo 'Job 1: Starting'; sleep 3; echo 'Job 1: Done'" --name "Test Job 1"
./jq add "echo 'Job 2: Starting'; sleep 2; echo 'Job 2: Done'" --name "Test Job 2"
./jq add "echo 'Job 3: Starting'; sleep 1; echo 'Job 3: Done'" --name "Test Job 3"

echo -e "\n2. Checking status..."
./jq status

echo -e "\n3. Starting worker in background..."
./jq worker &
WORKER_PID=$!

echo "Worker started with PID: $WORKER_PID"
echo "Waiting for jobs to complete..."

sleep 8

echo -e "\n4. Final status:"
./jq status

echo -e "\n5. Logs:"
./jq logs --lines 10

echo -e "\n6. Stopping worker..."
kill $WORKER_PID 2>/dev/null

echo -e "\nTest completed!"