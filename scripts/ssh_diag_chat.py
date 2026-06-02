import paramiko

HOST, PASS = "193.233.112.32", "CIad32fk6CaE"
cmds = [
    "grep DATABASE_URL /opt/chat/.env",
    "systemctl status asyncgram-chat --no-pager -l",
    "journalctl -u asyncgram-chat -n 40 --no-pager",
    "journalctl -u asyncgram-auth -n 15 --no-pager",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PASS, timeout=45)
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    o.channel.recv_exit_status()
    print("===", cmd)
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print("ERR:", err)
c.close()
