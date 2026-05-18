from __future__ import annotations

import io
import os
import sys
import tarfile
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("Установите paramiko: py -m pip install paramiko", file=sys.stderr)
    sys.exit(1)

HOST = os.environ.get("CHAT_DEPLOY_HOST", "")
USER = os.environ.get("CHAT_DEPLOY_USER", "root")
REMOTE_ROOT = os.environ.get("CHAT_DEPLOY_REMOTE", "/opt/chat").rstrip("/")
PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "")

REPO_ROOT = Path(__file__).resolve().parents[1]

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".idea",
        ".cursor",
        ".venv",
        "venv",
    }
)


def path_has_skipped_part(rel: Path) -> bool:
    return any(p in SKIP_DIR_NAMES for p in rel.parts)


def collect_files() -> list[tuple[Path, Path]]:
    out: list[tuple[Path, Path]] = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT, topdown=True):
        dp = Path(dirpath)
        rel_dir = dp.relative_to(REPO_ROOT)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        if path_has_skipped_part(rel_dir):
            continue
        for name in filenames:
            if name == ".__deploy_chat.tgz":
                continue
            p = dp / name
            rel = p.relative_to(REPO_ROOT)
            if path_has_skipped_part(rel):
                continue
            out.append((p, rel))
    return out


def main() -> None:
    if not HOST:
        print("Задайте CHAT_DEPLOY_HOST", file=sys.stderr)
        sys.exit(1)
    if not PASSWORD:
        print("Задайте CHAT_DEPLOY_PASSWORD", file=sys.stderr)
        sys.exit(1)

    files = collect_files()
    if not files:
        print("Нет файлов для упаковки", file=sys.stderr)
        sys.exit(1)

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tf:
        for abs_path, rel in sorted(files, key=lambda x: str(x[1]).lower()):
            arc = str(rel).replace("\\", "/")
            tf.add(abs_path, arcname=arc, recursive=False)
    data = buf.getvalue()
    print(f"Архив: {len(data)} байт, файлов: {len(files)}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)

    prep = (
        f"mkdir -p {REMOTE_ROOT} && "
        f"find {REMOTE_ROOT} -mindepth 1 -maxdepth 1 "
        f"! -name '.env' ! -name 'venv' ! -name '.venv' ! -name 'uploads' ! -name 'database.db' "
        f"-exec rm -rf {{}} +"
    )
    _, stdout, stderr = client.exec_command(prep)
    rc = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace")
    if rc != 0:
        print(f"Подготовка каталога: rc={rc}\n{err}", file=sys.stderr)
        client.close()
        sys.exit(1)

    remote_tar = f"{REMOTE_ROOT}/.__deploy_chat.tgz"
    sftp = client.open_sftp()
    try:
        with sftp.file(remote_tar, "wb") as rf:
            rf.write(data)
    finally:
        sftp.close()

    unpack = f"cd {REMOTE_ROOT} && tar xzf .__deploy_chat.tgz && rm -f .__deploy_chat.tgz"
    _, stdout, stderr = client.exec_command(unpack)
    rc = stdout.channel.recv_exit_status()
    out_b = stdout.read().decode("utf-8", errors="replace")
    err_b = stderr.read().decode("utf-8", errors="replace")
    client.close()

    if rc != 0:
        print(f"Распаковка: rc={rc}\n{err_b}\n{out_b}", file=sys.stderr)
        sys.exit(1)

    print(f"Готово: {USER}@{HOST}:{REMOTE_ROOT}")


if __name__ == "__main__":
    main()
