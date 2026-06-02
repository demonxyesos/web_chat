import paramiko
import sys

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
js = "/opt/chat/frontend/dist/assets/index-DMWI7h55.js"
for needle in ["admin-overlay", "__lobby__", "message_deleted", "cli-badge", "ADMIN"]:
    _, o, e = c.exec_command(f"grep -F -c '{needle}' {js} || true")
    o.channel.recv_exit_status()
    count = o.read().decode().strip()
    print(f"{needle}: {count}")
c.close()
