import paramiko

HOST, USER, PASS = "193.233.112.32", "root", "CIad32fk6CaE"
cmds = [
    "systemctl is-active asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin redis-server nginx",
    'curl -s -o /dev/null -w "health:%{http_code}" http://127.0.0.1:8001/health',
    'curl -s -o /dev/null -w "site:%{http_code}" -H "Host: proxy-mamont.click" http://127.0.0.1/',
    'curl -s -o /dev/null -w "ip:%{http_code}" http://127.0.0.1/ 2>&1 || echo ip_closed',
    "ls -la /etc/nginx/sites-enabled/",
    "head -35 /etc/nginx/sites-available/asyncgram.conf",
    "grep DATABASE_URL /opt/chat/.env; grep CORS_ORIGINS /opt/chat/.env",
    "journalctl -u asyncgram-auth -n 12 --no-pager",
    "journalctl -u asyncgram-chat -n 8 --no-pager",
    "ls -la /opt/chat/database.db /opt/chat/",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=45)
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    o.channel.recv_exit_status()
    print("===", cmd)
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print("ERR:", err)
c.close()
