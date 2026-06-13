"""In-process WebSocket room manager for match chat.

One room per match_id; a persisted message is broadcast to every open socket in
that room. Single-process only — to scale across workers, back this with Redis
pub/sub (the design's scale path); the connect/disconnect/broadcast interface
stays the same.
"""

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, match_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms[match_id].add(ws)

    def disconnect(self, match_id: int, ws: WebSocket) -> None:
        room = self._rooms.get(match_id)
        if room is not None:
            room.discard(ws)
            if not room:
                self._rooms.pop(match_id, None)

    async def broadcast(self, match_id: int, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._rooms.get(match_id, ())):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - prune any socket that won't accept
                dead.append(ws)
        for ws in dead:
            self.disconnect(match_id, ws)


manager = ConnectionManager()
