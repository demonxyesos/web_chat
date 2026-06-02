import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
cmd = r"""
for f in /root/chat/database.db /root/otp/chat/database.db /opt/chat/database.db; do
  if [ -f "$f" ]; then echo -n "$f: "; wc -c < "$f"; fi
done
if [ -f /root/chat/database.db ] && [ "$(wc -c < /root/chat/database.db)" -gt 1000 ]; then
  cp -a /root/chat/database.db /opt/chat/database.db
  chown www-data:www-data /opt/chat/database.db
  chmod 664 /opt/chat/database.db
  echo restored_from_root_chat
  systemctl restart asyncgram-auth asyncgram-chat
  sleep 3
  curl -sf http://127.0.0.1:8001/health && echo ok
fi
"""
_, o, _ = c.exec_command(cmd, timeout=60)
o.channel.recv_exit_status()
print(o.read().decode())
c.close()
