import paramiko

fix = r"""
set -e
chgrp www-data /opt/chat
chmod 775 /opt/chat
chown www-data:www-data /opt/chat/database.db /opt/chat/uploads
chmod 664 /opt/chat/database.db
systemctl restart asyncgram-auth asyncgram-chat
sleep 4
systemctl is-active asyncgram-auth asyncgram-chat
curl -sf http://127.0.0.1:8001/health; echo
curl -sf http://127.0.0.1:8002/health; echo
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
_, o, e = c.exec_command(fix, timeout=60)
o.channel.recv_exit_status()
print(o.read().decode())
print(e.read().decode())
c.close()
