"""Hotfix: auth passwords, chat 500, .env JWT — upload changed files only."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import paramiko

HOST = "193.233.112.32"
PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "CIad32fk6CaE")
REMOTE = "/opt/chat"
ROOT = Path(__file__).resolve().parents[1]

FILES = [
    "packages/common/asyncgram_common/passwords.py",
    "services/auth_service/app/services.py",
    "services/chat_service/app/repositories.py",
    "services/chat_service/app/services.py",
    "frontend/src/api.js",
]


def main() -> None:
    subprocess.run(
        "npm run build",
        cwd=ROOT / "frontend",
        check=True,
        shell=True,
    )

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=90)

    sftp = c.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        sftp.put(str(local), f"{REMOTE}/{rel.replace(chr(92), '/')}")
    dist = ROOT / "frontend/dist"
    for p in dist.rglob("*"):
        if p.is_file():
            rel = p.relative_to(dist).as_posix()
            sftp.put(str(p), f"{REMOTE}/frontend/dist/{rel}")
    sftp.close()

    setup = f"""
set -e
grep -q '^JWT_SECRET=' {REMOTE}/.env || echo "JWT_SECRET=$(openssl rand -hex 32)" >> {REMOTE}/.env
grep -q '^REDIS_URL=' {REMOTE}/.env || echo 'REDIS_URL=redis://127.0.0.1:6379/0' >> {REMOTE}/.env
systemctl restart asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin
sleep 3
curl -s -X POST http://127.0.0.1:8001/auth/token -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=user1&password=12345678'
echo
curl -s http://127.0.0.1:8001/health
echo
"""
    _, o, e = c.exec_command(setup, timeout=120)
    o.channel.recv_exit_status()
    print(o.read().decode())
    if e.read().decode().strip():
        print(e.read().decode())
    c.close()
    print("Hotfix deployed")


if __name__ == "__main__":
    main()
