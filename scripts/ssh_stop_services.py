"""Stop and disable asyncgram services on a remote host."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = os.environ.get("CHAT_DEPLOY_HOST", "")
PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "")

STOP = """set -e
systemctl stop asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin 2>/dev/null || true
systemctl disable asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin 2>/dev/null || true
systemctl stop asyncgram 2>/dev/null || true
systemctl disable asyncgram 2>/dev/null || true

rm -f /etc/nginx/sites-enabled/asyncgram.conf
nginx -t && systemctl reload nginx || true

echo === stopped ===
systemctl is-active asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin asyncgram 2>&1 || true
"""


def main() -> int:
    if not HOST or not PASSWORD:
        print("CHAT_DEPLOY_HOST and CHAT_DEPLOY_PASSWORD required", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST,
        username="root",
        password=PASSWORD,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    _, stdout, stderr = client.exec_command(STOP, timeout=120)
    rc = stdout.channel.recv_exit_status()
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    print(f"rc={rc}")
    client.close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
