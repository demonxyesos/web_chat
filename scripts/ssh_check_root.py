import paramiko
import sys

DB = ("77.91.65.70", "gtOsPBmeNXpJ")
APP = ("193.233.112.32", "CIad32fk6CaE")

for label, host, password, cmd in [
    (
        "db",
        DB[0],
        DB[1],
        r"""sudo -u postgres psql -d asyncgram -c "SELECT id, username, name, role, is_deleted FROM auth.users WHERE username = 'root';" """,
    ),
    (
        "app",
        APP[0],
        APP[1],
        "journalctl -u asyncgram-auth -n 8 --no-pager | tail -5",
    ),
]:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username="root", password=password, timeout=45)
    _, o, e = c.exec_command(cmd)
    o.channel.recv_exit_status()
    sys.stdout.buffer.write(f"=== {label} ===\n".encode())
    sys.stdout.buffer.write(o.read())
    err = e.read()
    if err:
        sys.stdout.buffer.write(err)
    c.close()
