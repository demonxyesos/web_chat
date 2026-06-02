import os
import sys

import paramiko

HOST = os.environ.get("CHAT_DEPLOY_HOST", "77.91.65.70")
PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "")

SETUP = """set -e
systemctl stop asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin

rm -f /opt/chat/database.db
touch /opt/chat/database.db
chown www-data:www-data /opt/chat/database.db
chmod 664 /opt/chat/database.db

systemctl start asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin
sleep 3

echo === services ===
systemctl is-active asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin

echo === db stats ===
python3 << 'PYEOF'
import sqlite3
db = sqlite3.connect("/opt/chat/database.db")
cur = db.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)
for table in ("users", "chats", "messages", "chat_members"):
    if table in tables:
        print(f"{table}:", cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
PYEOF
"""


VERIFY = """python3 << 'PYEOF'
import sqlite3
db = sqlite3.connect("/opt/chat/database.db")
cur = db.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)
for table in ("users", "chats", "messages", "chat_members"):
    if table in tables:
        print(f"{table}:", cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
if "users" in tables:
    print("user rows:", list(cur.execute("SELECT id, username FROM users")))
PYEOF
"""


RESTART_CHAT = """systemctl restart asyncgram-chat
sleep 2
""" + VERIFY


def verify_only(restart_chat: bool = False) -> int:
    if not PASSWORD:
        print("CHAT_DEPLOY_PASSWORD is required", file=sys.stderr)
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
    _, stdout, stderr = client.exec_command(RESTART_CHAT if restart_chat else VERIFY, timeout=60)
    rc = stdout.channel.recv_exit_status()
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    print(f"rc={rc}")
    client.close()
    return rc


def main() -> int:
    if not PASSWORD:
        print("CHAT_DEPLOY_PASSWORD is required", file=sys.stderr)
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
    _, stdout, stderr = client.exec_command(SETUP, timeout=120)
    rc = stdout.channel.recv_exit_status()
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    print(f"rc={rc}")
    client.close()
    return rc


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        raise SystemExit(verify_only())
    if len(sys.argv) > 1 and sys.argv[1] == "fix-chat":
        raise SystemExit(verify_only(restart_chat=True))
    raise SystemExit(main())
