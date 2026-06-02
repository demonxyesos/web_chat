import paramiko

HOST, USER, PASS = "193.233.112.32", "root", "CIad32fk6CaE"
fix = r"""
set -e
cd /opt/chat
mkdir -p uploads
touch database.db
chmod 664 database.db
chmod 775 .
chown -R www-data:www-data /opt/chat/database.db /opt/chat/uploads
sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://proxy-mamont.click,https://www.proxy-mamont.click|' /opt/chat/.env
systemctl restart asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin
sleep 3
systemctl is-active asyncgram-auth asyncgram-chat
curl -sf http://127.0.0.1:8001/health && echo auth_ok
curl -sf http://127.0.0.1:8002/health && echo chat_ok
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=45)
_, o, e = c.exec_command(fix, timeout=60)
rc = o.channel.recv_exit_status()
print(o.read().decode())
print(e.read().decode())
print("exit", rc)
c.close()
