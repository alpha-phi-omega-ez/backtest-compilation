#!/bin/bash

while true; do
    current_hour=$(date +%H)
    echo "Current hour: $current_hour"
    if [ $current_hour -ge 23 ] || [ $current_hour -lt 15 ]; then
        echo "Sleeping for 1 hour"
        sleep 3600
    else
        echo "Running main.py"
        uv run main.py
        echo "Sleeping for 2 hours"
        sleep 7200
    fi
done