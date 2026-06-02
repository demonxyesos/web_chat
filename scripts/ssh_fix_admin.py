import paramiko
import sys

APP = ("193.233.112.32", "CIad32fk6CaE")
DB = ("77.91.65.70", "gtOsPBmeNXpJ")

promote = r"""
sudo -u postgres psql -d asyncgram -v ON_ERROR_STOP=1 <<'PSQL'
UPDATE auth.users SET role = 'admin'
WHERE id = (
  SELECT id FROM auth.users
  WHERE username <> '__lobby__' AND is_deleted = 0
  ORDER BY id ASC
  LIMIT 1
);
SELECT id, username, role FROM auth.users ORDER BY id;
PSQL
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(DB[0], username="root", password=DB[1], timeout=45)
_, o, e = c.exec_command(promote)
o.channel.recv_exit_status()
sys.stdout.buffer.write(b"=== promote first real user ===\n")
sys.stdout.buffer.write(o.read())
sys.stdout.buffer.write(e.read())
c.close()

restart = """
systemctl restart asyncgram-auth asyncgram-chat asyncgram-ws
sleep 3
systemctl is-active asyncgram-auth asyncgram-chat asyncgram-ws
curl -sf http://127.0.0.1:8001/health; echo
curl -sf http://127.0.0.1:8002/health; echo
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(APP[0], username="root", password=APP[1], timeout=45)
_, o, e = c.exec_command(restart)
o.channel.recv_exit_status()
sys.stdout.buffer.write(b"=== restart app services ===\n")
sys.stdout.buffer.write(o.read())
sys.stdout.buffer.write(e.read())
c.close()
