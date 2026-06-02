import paramiko
import sys

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
js = "/opt/chat/frontend/dist/assets/index-D5KpEFJv.js"
for needle in ["unread_by_peer_user_", "message.created", "admin-overlay"]:
    _, o, e = c.exec_command(f"grep -F -c '{needle}' {js} || true")
    o.channel.recv_exit_status()
    print(f"{needle}: {o.read().decode().strip()}")
c.close()
