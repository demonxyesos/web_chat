from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
sftp = c.open_sftp()
sftp.put(
    str(ROOT / "services/chat_service/app/main.py"),
    "/opt/chat/services/chat_service/app/main.py",
)
sftp.close()
_, o, _ = c.exec_command(
    "chgrp www-data /opt/chat && chmod 775 /opt/chat && "
    "chown www-data:www-data /opt/chat/database.db /opt/chat/uploads && "
    "systemctl restart asyncgram-auth asyncgram-chat && sleep 4 && "
    "systemctl is-active asyncgram-auth asyncgram-chat && "
    "curl -sf http://127.0.0.1:8001/health && echo auth && "
    "curl -sf http://127.0.0.1:8002/health && echo chat",
    timeout=60,
)
o.channel.recv_exit_status()
print(o.read().decode())
c.close()
