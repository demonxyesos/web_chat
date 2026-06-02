import paramiko
import sys

HOST, PASS = "193.233.112.32", "CIad32fk6CaE"
DB_HOST, DB_PASS = "77.91.65.70", "gtOsPBmeNXpJ"

cmds_app = [
    "systemctl is-active redis-server asyncgram-ws asyncgram-chat",
    "grep -E '^(REDIS_URL|JWT_SECRET|DATABASE_URL)=' /opt/chat/.env",
    "journalctl -u asyncgram-ws -n 20 --no-pager",
    "journalctl -u asyncgram-chat -n 15 --no-pager",
    'curl -sf http://127.0.0.1:8003/health; echo',
]

cmds_db = [
    r"""sudo -u postgres psql -d asyncgram -c "SELECT id, username, name, role FROM auth.users ORDER BY id;" """,
]

for label, host, password, cmds in [
    ("app", HOST, PASS, cmds_app),
    ("db", DB_HOST, DB_PASS, cmds_db),
]:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username="root", password=password, timeout=45)
    print(f"===== {label} =====")
    for cmd in cmds:
        _, o, e = c.exec_command(cmd)
        o.channel.recv_exit_status()
        sys.stdout.buffer.write(f"--- {cmd}\n".encode())
        sys.stdout.buffer.write(o.read())
        err = e.read()
        if err:
            sys.stdout.buffer.write(err)
    c.close()
