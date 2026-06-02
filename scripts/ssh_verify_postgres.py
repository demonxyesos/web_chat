import paramiko
import sys

cmds = [
    ("app", "193.233.112.32", "CIad32fk6CaE", [
        "grep DATABASE_URL /opt/chat/.env",
        "systemctl is-active asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin",
        'curl -sf http://127.0.0.1:8001/health; echo',
        'curl -sf http://127.0.0.1:8002/health; echo',
    ]),
    ("db", "77.91.65.70", "gtOsPBmeNXpJ", [
        r"""sudo -u postgres psql -d asyncgram -c "\dn" """,
        r"""sudo -u postgres psql -d asyncgram -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('auth','chat') ORDER BY 1,2;" """,
        r"""sudo -u postgres psql -d asyncgram -c "SELECT COUNT(*) AS users FROM auth.users;" """,
        r"""sudo -u postgres psql -d asyncgram -c "SELECT username FROM auth.users;" """,
        r"""sudo -u postgres psql -d asyncgram -c "SELECT COUNT(*) AS chats FROM chat.chats;" """,
        r"""sudo -u postgres psql -d asyncgram -c "SELECT COUNT(*) AS messages FROM chat.messages;" """,
    ]),
]

for label, host, password, host_cmds in cmds:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username="root", password=password, timeout=45)
    print(f"===== {label} ({host}) =====")
    for cmd in host_cmds:
        _, o, e = c.exec_command(cmd)
        o.channel.recv_exit_status()
        sys.stdout.buffer.write(f"--- {cmd}\n".encode())
        sys.stdout.buffer.write(o.read())
        err = e.read()
        if err:
            sys.stdout.buffer.write(err)
    c.close()
