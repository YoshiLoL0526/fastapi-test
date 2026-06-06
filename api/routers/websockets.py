import uuid
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.core.security import JWTError, decode_token

router = APIRouter(prefix="/ws", tags=["websockets"])


class _ConnectionManager:
    def __init__(self) -> None:
        self._order_subs: dict[str, list[WebSocket]] = defaultdict(list)
        self._admin_subs: list[WebSocket] = []

    async def subscribe_order(self, order_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._order_subs[order_id].append(ws)

    def unsubscribe_order(self, order_id: str, ws: WebSocket) -> None:
        try:
            self._order_subs[order_id].remove(ws)
        except ValueError:
            pass

    async def push_order_update(self, order_id: str, payload: dict) -> None:
        for ws in list(self._order_subs.get(order_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                self.unsubscribe_order(order_id, ws)

    async def subscribe_admin(self, ws: WebSocket) -> None:
        await ws.accept()
        self._admin_subs.append(ws)

    def unsubscribe_admin(self, ws: WebSocket) -> None:
        try:
            self._admin_subs.remove(ws)
        except ValueError:
            pass

    async def push_stock_alert(self, payload: dict) -> None:
        for ws in list(self._admin_subs):
            try:
                await ws.send_json(payload)
            except Exception:
                self.unsubscribe_admin(ws)


manager = _ConnectionManager()


@router.websocket("/orders/{order_id}")
async def order_updates(websocket: WebSocket, order_id: uuid.UUID):
    """Subscribe to real-time status updates for a specific order.

    Send JWT as first message: {"token": "<access_token>"}
    Receives: {"order_id": "...", "status": "...", "updated_at": "..."}
    """
    await websocket.accept()
    try:
        auth_msg = await websocket.receive_json()
        token = auth_msg.get("token", "")
        try:
            decode_token(token)
        except JWTError:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    order_key = str(order_id)
    manager._order_subs[order_key].append(websocket)
    try:
        await websocket.send_json({"event": "subscribed", "order_id": order_key})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.unsubscribe_order(order_key, websocket)


@router.websocket("/admin/stock")
async def stock_alerts(websocket: WebSocket):
    """Subscribe to low-stock alerts (admin only).

    Send JWT as first message: {"token": "<access_token>"}
    Receives: {"event": "low_stock", "product_id": "...", "quantity_available": N}
    """
    await websocket.accept()
    try:
        auth_msg = await websocket.receive_json()
        token = auth_msg.get("token", "")
        try:
            payload = decode_token(token)
            if payload.get("role") != "admin":
                await websocket.send_json({"error": "Admin access required"})
                await websocket.close(code=1008)
                return
        except JWTError:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    manager._admin_subs.append(websocket)
    try:
        await websocket.send_json({"event": "subscribed", "channel": "stock_alerts"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.unsubscribe_admin(websocket)
