import os
import sys

try:
    import paramiko
except ImportError:
    print("pip install paramiko", file=sys.stderr)
    sys.exit(1)

HOST = os.environ.get("CHAT_DEPLOY_HOST", "")
USER = os.environ.get("CHAT_DEPLOY_USER", "root")
PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "")
REMOTE_ROOT = os.environ.get("CHAT_DEPLOY_REMOTE", "/opt/chat").rstrip("/")


def run(client: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    _, out, err = client.exec_command(cmd)
    rc = out.channel.recv_exit_status()
    return rc, out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")


def main() -> None:
    if not HOST:
        print("CHAT_DEPLOY_HOST", file=sys.stderr)
        sys.exit(1)
    if not PASSWORD:
        print("CHAT_DEPLOY_PASSWORD", file=sys.stderr)
        sys.exit(1)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    rc, o, e = run(client, f"ls -la {REMOTE_ROOT}")
    print(o or e)

    rc, o, e = run(
        client,
        "ls /etc/systemd/system/*.service 2>/dev/null | xargs -I{} basename {}",
    )
    units = [u.strip() for u in o.splitlines() if u.strip().endswith(".service")]
    candidates = [
        u
        for u in units
        if any(
            k in u.lower()
            for k in ("chat", "asyncgram", "uvicorn", "gunicorn", "fastapi", "gram")
        )
    ]
    print("candidates:", candidates or "(none by name)")

    rc, o, e = run(client, f"test -f {REMOTE_ROOT}/docker-compose.yml && echo yes || echo no")
    if "yes" in o:
        print(f"restart: docker compose in {REMOTE_ROOT}")
        rc, o, e = run(client, f"cd {REMOTE_ROOT} && docker compose restart 2>&1")
        print(o, e, "rc=", rc)
        client.close()
        sys.exit(0 if rc == 0 else 1)

    rc, o, e = run(client, "which supervisorctl 2>/dev/null && supervisorctl status 2>&1 | head -20")
    if "/supervisorctl" in o or o.strip().startswith("/"):
        print(o)

    for name in ("asyncgram", "chat", "uvicorn", "fastapi", "gunicorn"):
        unit = f"{name}.service"
        rc, o, e = run(client, f"systemctl cat {unit} 2>&1 | head -2")
        if rc == 0 and "[Unit]" in o:
            print(f"restart: systemctl restart {unit}")
            rc, o, e = run(client, f"systemctl restart {unit} && systemctl is-active {unit}")
            print(o, e, "rc=", rc)
            client.close()
            sys.exit(0 if rc == 0 else 1)

    rc, o, e = run(
        client,
        "systemctl list-units --type=service --state=running --no-pager 2>/dev/null",
    )
    for line in o.splitlines():
        low = line.lower()
        if "chat" in low or "asyncgram" in low or "uvicorn" in low:
            parts = line.split()
            if parts:
                unit = parts[0]
                print(f"try restart: {unit}")
                rc, o, e = run(client, f"systemctl restart {unit} && systemctl is-active {unit}")
                print(o, e, "rc=", rc)
                client.close()
                sys.exit(0 if rc == 0 else 1)

    print(f"Could not detect service; install systemd unit or docker-compose in {REMOTE_ROOT}")
    client.close()
    sys.exit(1)


if __name__ == "__main__":
    main()
