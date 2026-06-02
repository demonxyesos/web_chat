import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
_, o, _ = c.exec_command(
    "find /opt /root /var/backups -name '*.db' -size +1k 2>/dev/null | head -20"
)
o.channel.recv_exit_status()
print(o.read().decode())
c.close()
