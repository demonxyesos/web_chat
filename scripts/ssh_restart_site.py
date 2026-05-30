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

ASYNCGRAM_UNITS = [
    "asyncgram-auth.service",
    "asyncgram-chat.service",
    "asyncgram-ws.service",
    "asyncgram-media.service",
    "asyncgram-admin.service",
]


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

    for unit in ASYNCGRAM_UNITS:
        rc, o, e = run(client, f"systemctl cat {unit} 2>&1 | head -2")
        if rc == 0 and "[Unit]" in o:
            print(f"restart: systemctl restart {unit}")
            rc, o, e = run(
                client,
                f"systemctl restart {unit} && systemctl is-active {unit}",
            )
            print(o, e, "rc=", rc)

    rc, o, e = run(client, f"nginx -t 2>&1 && systemctl reload nginx 2>&1")
    print("nginx:", o or e, "rc=", rc)

    client.close()
    print("Done")


if __name__ == "__main__":
    main()
