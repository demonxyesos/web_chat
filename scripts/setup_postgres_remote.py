"""Install PostgreSQL on DB VPS and point chat app VPS at it."""
from __future__ import annotations

import os
import secrets
import sys
from urllib.parse import quote_plus

try:
    import paramiko
except ImportError:
    print("pip install paramiko", file=sys.stderr)
    sys.exit(1)

DB_HOST = os.environ.get("CHAT_DB_HOST", "77.91.65.70")
DB_ROOT_PASSWORD = os.environ.get("CHAT_DB_PASSWORD", "")
APP_HOST = os.environ.get("CHAT_DEPLOY_HOST", "193.233.112.32")
APP_PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "")
REMOTE = os.environ.get("CHAT_DEPLOY_REMOTE", "/opt/chat").rstrip("/")
DB_NAME = "asyncgram"
DB_USER = "asyncgram"
DB_PASS = os.environ.get("ASYNCGRAM_DB_PASSWORD", secrets.token_hex(16))


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    _, out, err = client.exec_command(cmd, timeout=timeout)
    rc = out.channel.recv_exit_status()
    return rc, out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")


def setup_postgres() -> None:
    print(f"1/3 PostgreSQL on {DB_HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        DB_HOST,
        username="root",
        password=DB_ROOT_PASSWORD,
        timeout=60,
        allow_agent=False,
        look_for_keys=False,
    )

    setup = f"""set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y postgresql postgresql-contrib

sudo -u postgres psql -v ON_ERROR_STOP=1 <<'PSQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{DB_USER}') THEN
    CREATE ROLE {DB_USER} LOGIN PASSWORD '{DB_PASS}';
  ELSE
    ALTER ROLE {DB_USER} WITH LOGIN PASSWORD '{DB_PASS}';
  END IF;
END
$$;
SELECT 'CREATE DATABASE {DB_NAME} OWNER {DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{DB_NAME}')\\gexec
PSQL

sudo -u postgres psql -d {DB_NAME} -v ON_ERROR_STOP=1 <<'PSQL'
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS chat;
GRANT ALL ON SCHEMA public TO {DB_USER};
GRANT ALL ON SCHEMA auth TO {DB_USER};
GRANT ALL ON SCHEMA chat TO {DB_USER};
ALTER SCHEMA auth OWNER TO {DB_USER};
ALTER SCHEMA chat OWNER TO {DB_USER};
ALTER DATABASE {DB_NAME} OWNER TO {DB_USER};
PSQL

PG_VER=$(ls /etc/postgresql | head -1)
PG_CONF="/etc/postgresql/$PG_VER/main/postgresql.conf"
PG_HBA="/etc/postgresql/$PG_VER/main/pg_hba.conf"

if grep -q "^[# ]*listen_addresses" "$PG_CONF"; then
  sed -i "s/^[# ]*listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"
else
  echo "listen_addresses = '*'" >> "$PG_CONF"
fi

grep -q "{APP_HOST}/32" "$PG_HBA" || \\
  echo "host    {DB_NAME}    {DB_USER}    {APP_HOST}/32    scram-sha-256" >> "$PG_HBA"

systemctl enable postgresql
systemctl restart postgresql

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow from {APP_HOST} to any port 5432 proto tcp
fi

echo === postgres ===
systemctl is-active postgresql
ss -ltnp | grep 5432 || netstat -ltnp | grep 5432
"""
    rc, out, err = run(client, setup, timeout=600)
    print(out)
    if err.strip():
        print("STDERR:", err)
    if rc != 0:
        client.close()
        raise SystemExit(f"postgres setup failed: {rc}")
    client.close()


def switch_app_server() -> None:
    print(f"2/3 Switch {APP_HOST} to remote PostgreSQL...")
    db_url = f"postgresql://{DB_USER}:{quote_plus(DB_PASS)}@{DB_HOST}:5432/{DB_NAME}"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        APP_HOST,
        username="root",
        password=APP_PASSWORD,
        timeout=60,
        allow_agent=False,
        look_for_keys=False,
    )

    switch = f"""set -e
grep -q '^DATABASE_URL=' {REMOTE}/.env && \\
  sed -i 's|^DATABASE_URL=.*|DATABASE_URL={db_url}|' {REMOTE}/.env || \\
  echo 'DATABASE_URL={db_url}' >> {REMOTE}/.env

echo '=== test connection ==='
{REMOTE}/venv/bin/python << 'PYEOF'
import os
from sqlalchemy import create_engine, text
url = open("{REMOTE}/.env").read().split("DATABASE_URL=")[1].split("\\n")[0].strip()
engine = create_engine(url, pool_pre_ping=True)
with engine.connect() as conn:
    print("postgres:", conn.execute(text("SELECT version()")).scalar()[:60])
PYEOF

systemctl restart asyncgram-auth asyncgram-chat
sleep 4

echo '=== services ==='
systemctl is-active asyncgram-auth asyncgram-chat
curl -sf http://127.0.0.1:8001/health
echo
curl -sf http://127.0.0.1:8002/health
echo
"""
    rc, out, err = run(client, switch, timeout=180)
    print(out)
    if err.strip():
        print("STDERR:", err)
    if rc != 0:
        client.close()
        raise SystemExit(f"app switch failed: {rc}")
    client.close()


def verify() -> None:
    print(f"3/3 Verify data on PostgreSQL ({DB_HOST})...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        DB_HOST,
        username="root",
        password=DB_ROOT_PASSWORD,
        timeout=60,
        allow_agent=False,
        look_for_keys=False,
    )
    verify_cmd = f"""sudo -u postgres psql -d {DB_NAME} -c "\\dn"
sudo -u postgres psql -d {DB_NAME} -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('auth','chat') ORDER BY 1,2;"
sudo -u postgres psql -d {DB_NAME} -c "SELECT COUNT(*) AS users FROM auth.users;"
sudo -u postgres psql -d {DB_NAME} -c "SELECT COUNT(*) AS chats FROM chat.chats;"
sudo -u postgres psql -d {DB_NAME} -c "SELECT COUNT(*) AS messages FROM chat.messages;"
"""
    rc, out, err = run(client, verify_cmd, timeout=60)
    print(out)
    if err.strip():
        print("STDERR:", err)
    client.close()
    if rc != 0:
        raise SystemExit(f"verify failed: {rc}")


def main() -> None:
    if not DB_ROOT_PASSWORD or not APP_PASSWORD:
        print("CHAT_DB_PASSWORD and CHAT_DEPLOY_PASSWORD required", file=sys.stderr)
        sys.exit(1)

    print(f"DB password for user '{DB_USER}': {DB_PASS}")
    setup_postgres()
    switch_app_server()
    verify()
    print("Done.")
    print(f"DATABASE_URL=postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}")


if __name__ == "__main__":
    main()
