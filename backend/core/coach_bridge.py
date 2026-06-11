import asyncio
import json
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Optional

try:
    import websockets
except Exception:  # pragma: no cover - covered by runtime state checks
    websockets = None


class CoachBridge:
    """Async WebSocket client that keeps AI Coach outside the main backend."""

    def __init__(
        self,
        enabled: bool,
        ws_url: str,
        session_id: str,
        reconnect_seconds: float = 3.0,
        request_timeout: float = 90.0,
        ping_interval: Optional[float] = None,
        ping_timeout: Optional[float] = None,
    ) -> None:
        self.enabled = enabled
        self.ws_url = ws_url
        self.session_id = session_id
        self.reconnect_seconds = max(0.5, float(reconnect_seconds))
        self.request_timeout = max(3.0, float(request_timeout))
        self.ping_interval = None if ping_interval is None or float(ping_interval) <= 0 else float(ping_interval)
        self.ping_timeout = None if ping_timeout is None or float(ping_timeout) <= 0 else float(ping_timeout)

        self.connected = False
        self.last_error: Optional[str] = None
        self.last_result: Optional[dict[str, Any]] = None
        self.last_result_at: Optional[str] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Task] = None
        self._ws: Any = None
        self._send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=3)
        self._pending: dict[str, asyncio.Future] = {}
        self._streams: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._analysis_in_flight = False
        self._analysis_request_ids: set[str] = set()
        self._lock = threading.Lock()

    async def start(self) -> None:
        if not self.enabled:
            self.last_error = "AI Coach disabled"
            return
        if websockets is None:
            self.last_error = "websockets package unavailable"
            return
        if self._task is not None and not self._task.done():
            return

        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        self.connected = False

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            connected = self.connected or self._ws is not None
            return {
                "enabled": self.enabled,
                "connected": connected,
                "ws_url": self.ws_url,
                "last_error": self.last_error,
                "last_result_at": self.last_result_at,
                "request_timeout": self.request_timeout,
                "ping_interval": self.ping_interval,
                "ping_timeout": self.ping_timeout,
            }

    def get_latest_result(self) -> Optional[dict[str, Any]]:
        with self._lock:
            if not self.connected and self._ws is None:
                return None
            return dict(self.last_result) if isinstance(self.last_result, dict) else None

    def submit_analysis(self, payload: dict[str, Any]) -> bool:
        if not self.enabled or self._loop is None or self._ws is None:
            return False
        request_id = str(uuid.uuid4())
        with self._lock:
            if self._analysis_in_flight:
                return False
            self._analysis_in_flight = True
            self._analysis_request_ids.add(request_id)

        message = {
            "type": "analysis.request",
            "request_id": request_id,
            "session_id": self.session_id,
            "payload": payload,
        }
        self._loop.call_soon_threadsafe(self._put_latest_analysis, message)
        return True

    async def chat(self, message: str, context: dict[str, Any], locale: str = "zh-TW") -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("AI Coach disabled")
        if self._ws is None:
            raise RuntimeError("AI Coach WebSocket not connected")

        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future

        await self._send_json(
            {
                "type": "chat.request",
                "request_id": request_id,
                "session_id": self.session_id,
                "payload": {
                    "message": message,
                    "context": context,
                    "semantic_context": context.get("semantic_context") if isinstance(context, dict) else None,
                    "locale": locale,
                },
            }
        )

        try:
            response = await asyncio.wait_for(future, timeout=self.request_timeout)
        finally:
            self._pending.pop(request_id, None)

        if response.get("type") == "coach.error":
            payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
            raise RuntimeError(str(payload.get("error") or "AI Coach request failed"))

        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError("AI Coach returned invalid response")
        return payload

    async def chat_stream(self, message: str, context: dict[str, Any], locale: str = "zh-TW"):
        if not self.enabled:
            raise RuntimeError("AI Coach disabled")
        if self._ws is None:
            raise RuntimeError("AI Coach WebSocket not connected")

        request_id = str(uuid.uuid4())
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._streams[request_id] = queue

        await self._send_json(
            {
                "type": "chat.request",
                "request_id": request_id,
                "session_id": self.session_id,
                "payload": {
                    "message": message,
                    "context": context,
                    "semantic_context": context.get("semantic_context") if isinstance(context, dict) else None,
                    "locale": locale,
                    "stream": True,
                },
            }
        )

        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=self.request_timeout)
                event_type = event.get("type")
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                if event_type == "coach.delta":
                    yield {"type": "delta", "delta": str(payload.get("delta") or "")}
                    continue
                if event_type == "coach.error":
                    raise RuntimeError(str(payload.get("error") or "AI Coach request failed"))
                if event_type == "coach.result":
                    yield {"type": "result", "payload": payload}
                    break
        finally:
            self._streams.pop(request_id, None)

    def _put_latest_analysis(self, message: dict[str, Any]) -> None:
        while self._send_queue.full():
            try:
                self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        try:
            self._send_queue.put_nowait(message)
        except asyncio.QueueFull:
            pass

    async def _run_forever(self) -> None:
        while True:
            ws_module = websockets
            if ws_module is None:
                self._set_status(connected=False, error="websockets package is unavailable")
                await asyncio.sleep(self.reconnect_seconds)
                continue
            try:
                async with ws_module.connect(
                    self.ws_url,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                ) as ws:
                    self._ws = ws
                    self._set_status(connected=True, error=None)
                    await asyncio.gather(self._send_loop(), self._recv_loop())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._set_status(connected=False, error=str(exc))
                self._clear_analysis_in_flight()
                await self._fail_pending(str(exc))
                await asyncio.sleep(self.reconnect_seconds)
            finally:
                self._ws = None
                self.connected = False

    async def _send_loop(self) -> None:
        while True:
            message = await self._send_queue.get()
            await self._send_json(message)

    async def _recv_loop(self) -> None:
        while True:
            raw = await self._ws.recv()
            message = json.loads(raw)
            msg_type = message.get("type")
            request_id = message.get("request_id")

            if request_id in self._streams:
                if msg_type == "coach.result":
                    payload = message.get("payload")
                    if isinstance(payload, dict):
                        self._store_result(payload)
                await self._streams[request_id].put(message)
                continue

            if request_id in self._pending:
                future = self._pending.get(request_id)
                if future is not None and not future.done():
                    future.set_result(message)
                continue

            if msg_type == "coach.result":
                payload = message.get("payload")
                if isinstance(payload, dict):
                    self._store_result(payload)
                if request_id in self._analysis_request_ids:
                    self._clear_analysis_in_flight(request_id)
            elif msg_type == "coach.error":
                payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
                self._set_status(connected=True, error=str(payload.get("error") or "AI Coach error"))
                if request_id in self._analysis_request_ids:
                    self._clear_analysis_in_flight(request_id)

    async def _send_json(self, message: dict[str, Any]) -> None:
        if self._ws is None:
            raise RuntimeError("AI Coach WebSocket not connected")
        await self._ws.send(json.dumps(message, ensure_ascii=False))

    async def _fail_pending(self, error: str) -> None:
        for future in list(self._pending.values()):
            if not future.done():
                future.set_exception(RuntimeError(error))
        self._pending.clear()
        for queue in list(self._streams.values()):
            await queue.put(
                {
                    "type": "coach.error",
                    "payload": {"error": error},
                }
            )
        self._streams.clear()

    def _store_result(self, result: dict[str, Any]) -> None:
        result = dict(result)
        result.setdefault("timestamp", datetime.now().isoformat())
        with self._lock:
            self.last_result = result
            self.last_result_at = result.get("timestamp") or datetime.now().isoformat()
            self.last_error = result.get("error")

    def _set_status(self, connected: bool, error: Optional[str]) -> None:
        with self._lock:
            self.connected = connected
            self.last_error = error

    def _clear_analysis_in_flight(self, request_id: Optional[str] = None) -> None:
        with self._lock:
            if request_id is not None:
                self._analysis_request_ids.discard(request_id)
            else:
                self._analysis_request_ids.clear()
            if not self._analysis_request_ids:
                self._analysis_in_flight = False
