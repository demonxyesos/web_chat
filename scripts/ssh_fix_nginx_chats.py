"""Fix nginx /chats routing and reload."""
from __future__ import annotations

import base64
from pathlib import Path

import paramiko

CONF = Path(__file__).resolve().parents[1] / "infra/nginx/asyncgram-production.conf"
HOST = "193.233.112.32"
PASSWORD = "CIad32fk6CaE"


def main() -> None:
    b64 = base64.b64encode(CONF.read_bytes()).decode()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=90)
    _, o, e = c.exec_command(
        f"""
set -e
echo {b64} | base64 -d > /etc/nginx/sites-available/asyncgram.conf
cp /etc/nginx/sites-available/asyncgram.conf /opt/chat/infra/nginx/asyncgram-production.conf
nginx -t && systemctl reload nginx
curl -s -o /dev/null -w 'chats_http:%{{http_code}} content_type:%{{content_type}}\\n' \\
  -H 'Host: proxy-mamont.click' http://127.0.0.1/chats \\
  -H 'Authorization: Bearer test' || true
""",
        timeout=60,
    )
    o.channel.recv_exit_status()
    print(o.read().decode())
    print(e.read().decode())
    c.close()


if __name__ == "__main__":
    main()
