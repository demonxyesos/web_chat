import paramiko
import sys

HOST, PASS = "193.233.112.32", "CIad32fk6CaE"

cmds = [
    "grep CHAT_DEPLOY_REMOTE /opt/chat/scripts/deploy_and_start.py 2>/dev/null | head -1 || echo no_local_script",
    "grep -E '^(WorkingDirectory|EnvironmentFile|ExecStart)=' /etc/systemd/system/asyncgram-auth.service",
    "grep -E '^(WorkingDirectory|EnvironmentFile|ExecStart)=' /etc/systemd/system/asyncgram-chat.service",
    "grep root /etc/nginx/sites-available/asyncgram.conf | head -5",
    "ls -la /opt/chat/ | head -20",
    "test -f /opt/chat/.env && echo '.env: OK' || echo '.env: MISSING'",
    "grep DATABASE_URL /opt/chat/.env",
    "readlink -f /opt/chat/services/auth_service/app/services.py",
    "stat -c '%y %n' /opt/chat/frontend/dist/assets/*.js 2>/dev/null | tail -1",
    "ps aux | grep -E 'uvicorn.*services' | grep -v grep",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PASS, timeout=45)
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    o.channel.recv_exit_status()
    sys.stdout.buffer.write(f"--- {cmd}\n".encode())
    sys.stdout.buffer.write(o.read())
    err = e.read()
    if err:
        sys.stdout.buffer.write(err)
c.close()
