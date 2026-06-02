import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
cmds = [
    "cat /etc/nginx/sites-available/asyncgram.conf",
    'curl -sI http://127.0.0.1/ -H "Host: proxy-mamont.click" | head -15',
    'curl -skI https://127.0.0.1/ -H "Host: proxy-mamont.click" | head -15',
    'curl -sI http://proxy-mamont.click/ 2>&1 | head -15',
    'curl -skI https://proxy-mamont.click/ 2>&1 | head -15',
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    o.channel.recv_exit_status()
    print("===", cmd)
    print(o.read().decode())
c.close()
