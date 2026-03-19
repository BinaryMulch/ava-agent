Server diagnostics:
When asked to diagnose performance issues, check the server, or figure out why something is slow or broken, follow this structured checklist:

1. System overview:
   - uptime
   - cat /proc/loadavg
   - Report if load average exceeds the number of CPU cores (nproc)

2. Top processes by CPU and memory:
   - ps aux --sort=-%cpu | head -15
   - ps aux --sort=-%mem | head -15
   - Flag anything using more than 50% CPU or 20% memory

3. Memory analysis:
   - free -h
   - Check if swap is being used heavily — this indicates memory pressure
   - If swap usage is high: swapon --show && cat /proc/swaps

4. Disk usage:
   - df -h
   - Flag any filesystem over 85% full
   - If a filesystem is nearly full, find the biggest offenders: du -sh /* 2>/dev/null | sort -rh | head -10

5. Disk I/O:
   - iostat -x 1 3 (if available, otherwise skip)
   - Flag any device with >80% utilization or high await times

6. Network:
   - ss -tlnp (listening ports and what process owns them)
   - ss -s (connection summary — look for high TIME_WAIT or CLOSE_WAIT counts)

7. Failed services:
   - systemctl --failed
   - Report any failed units and suggest checking their logs with journalctl -u <unit> -n 50

8. Recent kernel issues:
   - dmesg -T --level=err,warn | tail -30
   - Look for OOM kills, hardware errors, disk errors, or segfaults

9. Recent auth failures (potential intrusion attempts):
   - journalctl -u ssh --since "1 hour ago" --no-pager | grep -i "failed\|invalid" | tail -20
   - Report the count and top source IPs if any

Reporting guidelines:
- Lead with the most urgent finding (anything critical goes first)
- For each issue found, explain what it means in plain language and suggest a fix
- If everything looks healthy, say so clearly with key metrics (load, memory, disk)
- Don't dump raw command output unless the user asks — summarize findings