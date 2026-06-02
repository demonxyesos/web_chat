import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("193.233.112.32", username="root", password="CIad32fk6CaE", timeout=45)
for cmd in [
    'curl -sk -o /dev/null -w "https_local:%{http_code}" https://127.0.0.1/ -H "Host: proxy-mamont.click"',
    'curl -s -o /dev/null -w "http_domain:%{http_code}" http://proxy-mamont.click/',
    'curl -sk -o /dev/null -w "https_domain:%{http_code}" https://proxy-mamont.click/',
]:
    _, o, _ = c.exec_command(cmd)
    o.channel.recv_exit_status()
    print(o.read().decode())
c.close()
