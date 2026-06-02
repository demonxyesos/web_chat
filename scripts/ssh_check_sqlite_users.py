import paramiko
import sys

HOST, PASS = "193.233.112.32", "CIad32fk6CaE"

cmds = [
    r"""/opt/chat/venv/bin/python << 'PYEOF'
import sqlite3
c = sqlite3.connect('/opt/chat/database.db')
print('sqlite users:')
for row in c.execute("SELECT id, username, role FROM users ORDER BY id"):
    print(row)
PYEOF""",
    "grep DATABASE_URL /opt/chat/.env",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PASS, timeout=45)
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    o.channel.recv_exit_status()
    sys.stdout.buffer.write(f"--- {cmd[:60]}\n".encode())
    sys.stdout.buffer.write(o.read())
c.close()
