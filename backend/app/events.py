"""实时事件发射器 / Real-time event emitter."""
from __future__ import annotations

import json
import threading
import queue
from typing import Dict, List, Callable, Any


class EventEmitter:
    """线程安全的事件发射器，支持 SSE 客户端订阅."""

    def __init__(self):
        self._clients: Dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def emit(self, event: str, payload: Any) -> None:
        data = json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
        with self._lock:
            for q in list(self._clients.values()):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass

    def subscribe(self) -> queue.Queue:
        with self._lock:
            self._counter += 1
            cid = f"client-{self._counter}"
            q: queue.Queue = queue.Queue(maxsize=100)
            self._clients[cid] = q
            return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            for cid, client_q in list(self._clients.items()):
                if client_q is q:
                    del self._clients[cid]
                    break


# 全局事件发射器实例 / global event emitter instance
emitter = EventEmitter()
