"""Deploy chat list + notification fixes."""
from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path

import paramiko

HOST = "193.233.112.32"
PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "CIad32fk6CaE")
ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/opt/chat"


def main() -> None:
    subprocess.run("npm run build", cwd=ROOT / "frontend", check=True, shell=True)

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=90)

    sftp = c.open_sftp()
    for rel in ["frontend/src/api.js", "frontend/src/Chat.jsx", "infra/nginx/asyncgram-production.conf"]:
        sftp.put(str(ROOT / rel), f"{REMOTE}/{rel}")
    for p in (ROOT / "frontend/dist").rglob("*"):
        if p.is_file():
            rel = p.relative_to(ROOT / "frontend/dist").as_posix()
            sftp.put(str(p), f"{REMOTE}/frontend/dist/{rel}")
    sftp.close()

    b64 = base64.b64encode((ROOT / "infra/nginx/asyncgram-production.conf").read_bytes()).decode()
    _, o, _ = c.exec_command(
        f"echo {b64} | base64 -d > /etc/nginx/sites-available/asyncgram.conf && nginx -t && systemctl reload nginx",
        timeout=60,
    )
    o.channel.recv_exit_status()
    print(o.read().decode())
    c.close()
    print("Deployed")


if __name__ == "__main__":
    main()
