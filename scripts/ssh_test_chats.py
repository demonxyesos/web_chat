import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=60)
_, o, _ = c.exec_command(
    "curl -s -X POST http://127.0.0.1:8001/auth/token "
    "-H 'Content-Type: application/x-www-form-urlencoded' "
    "-d 'username=user1&password=12345678'"
)
o.channel.recv_exit_status()
tok = json.loads(o.read().decode())["access_token"]
for path, port in [("/users/me", 8001), ("/chats", 8002)]:
    _, o, _ = c.exec_command(
        f"curl -s -w '\\nHTTP:%{{http_code}}' http://127.0.0.1:{port}{path} "
        f"-H 'Authorization: Bearer {tok}'"
    )
    o.channel.recv_exit_status()
    print(path, o.read().decode()[:400])
c.close()
