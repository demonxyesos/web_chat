import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)

cmds = [
    'curl -s -o /dev/null -w "domain:%{http_code}" -H "Host: proxy-mamont.click" http://127.0.0.1/',
    'curl -s -o /dev/null -w "ext:%{http_code}" http://proxy-mamont.click/ 2>/dev/null || echo ext_fail',
    "which certbot; test -f /etc/letsencrypt/live/proxy-mamont.click/fullchain.pem && echo has_cert || echo no_cert",
    "dig +short proxy-mamont.click A",
]
for cmd in cmds:
    _, o, _ = c.exec_command(cmd)
    o.channel.recv_exit_status()
    print(cmd, "->", o.read().decode().strip())

# try certbot if missing
_, o, _ = c.exec_command(
    "test -f /etc/letsencrypt/live/proxy-mamont.click/fullchain.pem || "
    "(command -v certbot >/dev/null && certbot certonly --nginx -d proxy-mamont.click -d www.proxy-mamont.click "
    "--non-interactive --agree-tos -m admin@proxy-mamont.click 2>&1 | tail -5)",
    timeout=120,
)
o.channel.recv_exit_status()
out = o.read().decode()
if out.strip():
    print("certbot:", out)

c.close()
