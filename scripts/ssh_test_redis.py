import asyncio
import json
import paramiko
import sys

HOST, PASS = "193.233.112.32", "CIad32fk6CaE"

test = r"""
/opt/chat/venv/bin/python << 'PYEOF'
import asyncio
import json
from asyncgram_common.constants import CHAT_EVENTS_CHANNEL
from asyncgram_common.events import ChatEvent
from asyncgram_common.redis_bus import EventBus

async def main():
    bus = EventBus("redis://127.0.0.1:6379/0")
    await bus.connect()
    got = asyncio.get_event_loop().create_future()

    async def handler(event: ChatEvent):
        if not got.done():
            got.set_result(event.model_dump())

    task = asyncio.create_task(bus.subscribe(handler))
    await asyncio.sleep(0.5)
    test = ChatEvent(
        type="message.created",
        broadcast=False,
        target_user_ids=[2, 3],
        payload={"id": 999, "chat_id": 1, "content": "ping", "author": {"username": "a"}, "recipient": {"username": "b"}},
    )
    await bus.publish(test)
    try:
        result = await asyncio.wait_for(got, timeout=3)
        print("redis_ok", json.dumps(result)[:120])
    except asyncio.TimeoutError:
        print("redis_fail timeout")
    task.cancel()
    await bus.close()

asyncio.run(main())
PYEOF
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PASS, timeout=45)
_, o, e = c.exec_command(f"cd /opt/chat && export PYTHONPATH=/opt/chat:/opt/chat/packages/common && {test}")
o.channel.recv_exit_status()
sys.stdout.buffer.write(o.read())
sys.stdout.buffer.write(e.read())
c.close()
