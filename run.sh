#!/bin/bash

while true; do
    uv run main.py
    current_hour=$(date +%H)
    if [ $current_hour -ge 22 ] || [ $current_hour -lt 6 ]; then
        echo "Sleeping for 8 hours"
        sleep 28800
    else
        echo "Sleeping for 2.5 hours"
        sleep 9000
    fi
done