"""Deploy HTTP-only nginx (no HTTPS redirect) — TLS via Cloudflare."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import paramiko

HOST = "193.233.112.32"
PASSWORDS = ["CIad32fk6CaE", "CIad32fk6Ca"]
CONF = Path(__file__).resolve().parents[1] / "infra/nginx/asyncgram-production.conf"


def connect() -> paramiko.SSHClient:
    last: Exception | None = None
    for pwd in PASSWORDS:
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, username="root", password=pwd, timeout=90, banner_timeout=90)
            return c
        except Exception as e:
            last = e
    raise SystemExit(f"SSH failed: {last}")


def main() -> None:
    b64 = base64.b64encode(CONF.read_bytes()).decode()
    c = connect()
    _, o, e = c.exec_command(
        f"""
set -e
echo {b64} | base64 -d > /etc/nginx/sites-available/asyncgram.conf
cp /etc/nginx/sites-available/asyncgram.conf /opt/chat/infra/nginx/asyncgram-production.conf
ln -sf /etc/nginx/sites-available/asyncgram.conf /etc/nginx/sites-enabled/asyncgram.conf
rm -f /etc/nginx/sites-enabled/chat /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
curl -sI http://127.0.0.1/ -H 'Host: proxy-mamont.click' | head -4
""",
        timeout=90,
    )
    rc = o.channel.recv_exit_status()
    print(o.read().decode())
    err = e.read().decode()
    if err:
        print(err, file=sys.stderr)
    c.close()
    sys.exit(rc)


if __name__ == "__main__":
    main()
