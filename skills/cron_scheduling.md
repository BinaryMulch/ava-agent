Cron job management:
When asked to create, list, edit, or remove scheduled tasks, follow these practices:

Listing cron jobs:
- Show the current user's crontab: crontab -l
- Show root's crontab: crontab -u root -l
- Show system cron files: ls -la /etc/cron.d/ && cat /etc/crontab
- Show timer-based schedules: systemctl list-timers --all

Creating cron jobs:
- Always use crontab -e style editing via a temp file to avoid clobbering:
  1. crontab -l > /tmp/crontab_backup 2>/dev/null || true
  2. Add the new line to /tmp/crontab_backup
  3. crontab /tmp/crontab_backup
  4. Verify with crontab -l
- Always include a comment line above each job explaining what it does:
  # Description of what this job does - added YYYY-MM-DD
- Always set PATH at the top of the crontab if not already present:
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
- Always redirect output to a log file to capture errors:
  0 3 * * * /path/to/script.sh >> /var/log/cron-jobname.log 2>&1
- For scripts, ensure they are executable: chmod +x /path/to/script.sh
- Place custom scripts in /opt/scripts/ or /usr/local/bin/ — not in /tmp/

Cron schedule syntax reference (for your own use when building expressions):
- minute(0-59) hour(0-23) day-of-month(1-31) month(1-12) day-of-week(0-7, 0 and 7 are Sunday)
- Common patterns:
  - Every 5 minutes: */5 * * * *
  - Daily at 3am: 0 3 * * *
  - Every Monday at 8am: 0 8 * * 1
  - First of month at midnight: 0 0 1 * *
  - Every hour: 0 * * * *
  - Weekdays at 6pm: 0 18 * * 1-5

Editing and removing cron jobs:
- To edit: dump crontab to file, modify, reload (same as create flow)
- To remove a specific job: dump, delete the relevant lines, reload
- To remove ALL jobs for a user: crontab -r (confirm with user first — this is destructive)
- Always back up before editing: crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S)

Important rules:
- Always confirm the schedule with the user in plain language before creating ("This will run every day at 3am — correct?")
- Always verify the job was added correctly by running crontab -l after
- Never use crontab -r without explicit user confirmation
- When creating scripts for cron, always use absolute paths for all commands
- Warn the user that cron runs in a minimal environment — PATH, HOME, and other variables may not be set