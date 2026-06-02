import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
cmd = "find /opt/chat -name '*.db*' -o -name 'database*' 2>/dev/null; ls -la /opt/chat/backend/*.db 2>/dev/null; wc -c /opt/chat/database.db"
_, o, _ = c.exec_command(cmd)
o.channel.recv_exit_status()
print(o.read().decode())
c.close()
