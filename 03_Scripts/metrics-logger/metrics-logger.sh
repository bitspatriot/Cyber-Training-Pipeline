#!/usr/bin/env bash
# Appends timestamped CPU and RAM usage to the metrics log every 30s.
set -euo pipefail

LOGFILE="/mnt/log_data/metrics.log"
INTERVAL=30

while true; do
    TS="$(date '+%Y-%m-%d %H:%M:%S')"

    # CPU usage %: 100 minus idle, read from top's aggregate line
    CPU="$(top -bn1 | awk -F',' '/%Cpu/ {for(i=1;i<=NF;i++) if($i ~ /id/){gsub(/[^0-9.]/,"",$i); printf "%.1f", 100-$i}}')"

    # RAM usage: used/total in MB plus percentage, from free
    RAM="$(free -m | awk '/^Mem:/ {printf "%d/%dMB (%.1f%%)", $3, $2, ($3/$2)*100}')"

    echo "${TS} CPU:${CPU}% RAM:${RAM}" >> "$LOGFILE"

    sleep "$INTERVAL"
done