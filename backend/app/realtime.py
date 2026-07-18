"""SSE broker: one asyncio queue per connected client.

Routes run in FastAPI's threadpool (sync def), so publish() hops onto the
event loop with call_soon_threadsafe.
"""
import asyncio
import json

from .models import Role, User


class Broker:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        # queue -> (user_id, role)
        self.subscribers: dict[asyncio.Queue, tuple[int, Role]] = {}

    def subscribe(self, user: User) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers[q] = (user.id, user.role)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subscribers.pop(q, None)

    def publish(self, event: dict, *, to_agents: bool = False, to_user_id: int | None = None):
        if self.loop is None:
            return
        payload = json.dumps(event)
        for q, (user_id, role) in list(self.subscribers.items()):
            if (to_agents and role == Role.agent) or (to_user_id is not None and user_id == to_user_id):
                self.loop.call_soon_threadsafe(q.put_nowait, payload)


broker = Broker()
