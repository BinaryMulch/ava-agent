Self-maintenance and health checks:
When asked to check your health, maintain yourself, or clean up, follow these steps:

1. Check your own logs for recent errors:
   - tail -100 {repo_dir}/data/logs/ava-agent.log | grep -i "error\|exception\|warning\|traceback"
   - Report any recurring issues or patterns

2. Check database size and integrity:
   - ls -lh {repo_dir}/data/conversations.db
   - sqlite3 {repo_dir}/data/conversations.db "PRAGMA integrity_check;"
   - sqlite3 {repo_dir}/data/conversations.db "SELECT COUNT(*) FROM conversations;"
   - sqlite3 {repo_dir}/data/conversations.db "SELECT COUNT(*) FROM messages;"

3. Check disk usage of your data directory:
   - du -sh {repo_dir}/data/
   - du -sh {repo_dir}/data/uploads/
   - du -sh {repo_dir}/data/ava_files/
   - du -sh {repo_dir}/data/logs/

4. Check for orphaned files (uploaded images not referenced by any message):
   - List files in data/uploads/ and cross-reference with image metadata in the database
   - sqlite3 {repo_dir}/data/conversations.db "SELECT images FROM messages WHERE images IS NOT NULL;"
   - Report any orphaned files and their sizes, but DO NOT delete them without explicit permission

5. Check for stale ava_files (images you downloaded that may no longer be needed):
   - find {repo_dir}/data/ava_files/ -type f -mtime +30 -ls
   - Report old files and their sizes, but DO NOT delete them without explicit permission

6. Check service status:
   - systemctl status {service_name}
   - Report uptime, memory usage, and any restart history

7. Check for empty conversations (no messages):
   - sqlite3 {repo_dir}/data/conversations.db "SELECT id, title FROM conversations WHERE id NOT IN (SELECT DISTINCT conversation_id FROM messages);"
   - Report them, but DO NOT delete without explicit permission

Important rules:
- NEVER delete data without the user explicitly asking you to
- Always report what you find and recommend actions, then wait for approval
- When the user approves a cleanup action, confirm what will be deleted and the disk space that will be freed before proceeding
- After any cleanup, report what was removed and the new disk usage