import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
_, o, _ = c.exec_command(
    "/opt/chat/venv/bin/python -c \"import sqlite3; c=sqlite3.connect('/opt/chat/database.db'); "
    "print('tables:', [r[0] for r in c.execute(\\\"select name from sqlite_master where type='table'\\\")]); "
    "print('users:', c.execute('select count(*) from users').fetchone()[0])\""
)
o.channel.recv_exit_status()
print(o.read().decode())
c.close()
