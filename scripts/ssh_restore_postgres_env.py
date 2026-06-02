import paramiko
import sys

HOST, PASS = "193.233.112.32", "CIad32fk6CaE"
DB_PASS = "ec0171acb8c4b649f74248cb76114d45"
PG_URL = f"postgresql://asyncgram:{DB_PASS}@77.91.65.70:5432/asyncgram"

fix = f"""set -e
sed -i 's|^DATABASE_URL=.*|DATABASE_URL={PG_URL}|' /opt/chat/.env
grep DATABASE_URL /opt/chat/.env
systemctl restart asyncgram-auth asyncgram-chat asyncgram-ws
sleep 3
systemctl is-active asyncgram-auth asyncgram-chat
curl -sf http://127.0.0.1:8001/health; echo
curl -sf http://127.0.0.1:8002/health; echo
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PASS, timeout=45)
_, o, e = c.exec_command(fix)
o.channel.recv_exit_status()
sys.stdout.buffer.write(o.read())
sys.stdout.buffer.write(e.read())
c.close()
