import asyncio
import json
import paramiko
import sys

HOST, PASS = "193.233.112.32", "CIad32fk6CaE"

script = r"""
cd /opt/chat
export PYTHONPATH=/opt/chat:/opt/chat/packages/common
/opt/chat/venv/bin/python << 'PYEOF'
import asyncio
import json
import urllib.parse
import urllib.request

from asyncgram_common.constants import CHAT_EVENTS_CHANNEL
from asyncgram_common.events import ChatEvent
from asyncgram_common.redis_bus import EventBus

BASE = "http://127.0.0.1"


def token_for(username, password):
    data = urllib.parse.urlencode(
        {"username": username, "password": password, "grant_type": "password"}
    ).encode()
    req = urllib.request.Request(
        f"{BASE}:8001/auth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.load(resp)
    return body["access_token"], body["user"]


async def listen_once():
    bus = EventBus("redis://127.0.0.1:6379/0")
    await bus.connect()
    fut = asyncio.get_event_loop().create_future()

    async def handler(event: ChatEvent):
        if event.type == "message.created" and not fut.done():
            fut.set_result(event)

    task = asyncio.create_task(bus.subscribe(handler))
    await asyncio.sleep(0.3)

    token, user = token_for("user1", "user1")
    payload = json.dumps({"content": "ws-test", "to": "root", "reply_to_id": None}).encode()
    req = urllib.request.Request(
        f"{BASE}:8002/messages",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        created = json.load(resp)
    print("created_id", created.get("id"))

    try:
        event = await asyncio.wait_for(fut, timeout=5)
        print("event_targets", event.target_user_ids)
        print("payload_author", event.payload.get("author", {}).get("username"))
        print("payload_recipient", event.payload.get("recipient", {}).get("username"))
    except asyncio.TimeoutError:
        print("NO_REDIS_EVENT")

    task.cancel()
    await bus.close()

asyncio.run(listen_once())
PYEOF
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PASS, timeout=45)
_, o, e = c.exec_command(script, timeout=120)
o.channel.recv_exit_status()
sys.stdout.buffer.write(o.read())
sys.stdout.buffer.write(e.read())
c.close()
