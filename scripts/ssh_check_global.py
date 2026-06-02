import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=60)

for user, pwd in [("user1", "12345678"), ("user2", "12345678")]:
    _, o, _ = c.exec_command(
        "curl -s -X POST http://127.0.0.1:8001/auth/token "
        "-H 'Content-Type: application/x-www-form-urlencoded' "
        f"-d 'username={user}&password={pwd}'"
    )
    o.channel.recv_exit_status()
    tok = json.loads(o.read().decode())["access_token"]
    _, o, _ = c.exec_command(
        f"curl -s http://127.0.0.1:8002/chats -H 'Authorization: Bearer {tok}'"
    )
    o.channel.recv_exit_status()
    print(user, o.read().decode())

_, o, _ = c.exec_command(
    "/opt/chat/venv/bin/python -c \""
    "import sqlite3; c=sqlite3.connect('/opt/chat/database.db');"
    "print('chats', list(c.execute('select id,user_a_id,user_b_id,is_global,is_deleted from chats')));"
    "print('users', list(c.execute('select id,username,is_deleted from users')));"
    "print('lobby', list(c.execute(\\\"select id,username from users where username='__lobby__'\\\")));"
    "\""
)
o.channel.recv_exit_status()
print("db:", o.read().decode())
c.close()
