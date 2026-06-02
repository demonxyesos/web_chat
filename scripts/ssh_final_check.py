import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
cmds = [
    "systemctl is-active asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin nginx redis-server",
    'curl -s -o /dev/null -w "%{http_code}" http://193.233.112.32/ 2>&1 || echo closed',
    'curl -s -o /dev/null -w "%{http_code}" -H "Host: proxy-mamont.click" http://193.233.112.32/',
    "ls -la /etc/letsencrypt/live/proxy-mamont.click/ 2>&1 | head -3",
    "sqlite3 /opt/chat/database.db '.tables' 2>/dev/null || echo no_tables",
]
for cmd in cmds:
    _, o, _ = c.exec_command(cmd)
    o.channel.recv_exit_status()
    print(">", cmd)
    print(o.read().decode().strip())
c.close()
