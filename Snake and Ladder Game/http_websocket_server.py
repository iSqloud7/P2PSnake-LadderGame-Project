#!/usr/bin/env python3
"""
HTTP-based WebSocket сервер што може да работи со ngrok HTTP тунели
"""

import asyncio
import websockets
import json
import logging
from typing import Dict, Set
import uuid
from websockets.server import serve
from websockets.exceptions import ConnectionClosed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HTTPWebSocketServer:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.all_clients: Set = set()

    async def register_client(self, websocket):
        self.all_clients.add(websocket)
        logger.info(f"Client connected. Total: {len(self.all_clients)}")

    async def unregister_client(self, websocket):
        if websocket in self.all_clients:
            self.all_clients.remove(websocket)

        # Отстрани ги сесиите што содржат овој клиент
        sessions_to_remove = []
        for session_id, session_data in self.sessions.items():
            if websocket in session_data.values():
                sessions_to_remove.append(session_id)
                # Извести го другиот клиент
                for role, client in session_data.items():
                    if client != websocket and client in self.all_clients:
                        try:
                            await client.send(json.dumps({
                                "type": "peer_disconnected",
                                "session_id": session_id
                            }))
                        except:
                            pass

        for session_id in sessions_to_remove:
            del self.sessions[session_id]

        logger.info(f"Client disconnected. Remaining: {len(self.all_clients)}")

    async def handle_message(self, websocket, message):
        try:
            data = json.loads(message)
            message_type = data.get("type")
            logger.info(f"Message: {message_type}")

            if message_type == "create_session":
                await self.handle_create_session(websocket, data)
            elif message_type == "join_session":
                await self.handle_join_session(websocket, data)
            elif message_type == "game_message":
                await self.handle_game_message(websocket, data)

        except Exception as e:
            logger.error(f"Error: {e}")

    async def handle_create_session(self, websocket, data):
        session_id = str(uuid.uuid4())
        player_name = data.get("player_name", "Host")
        player_avatar = data.get("player_avatar", "🙂")

        self.sessions[session_id] = {
            "host": websocket,
            "guest": None,
            "host_info": {"name": player_name, "avatar": player_avatar}
        }

        invite_code = session_id[:8].upper()

        await websocket.send(json.dumps({
            "type": "session_created",
            "session_id": session_id,
            "invite_code": invite_code
        }))

        logger.info(f"Session created: {invite_code}")

    async def handle_join_session(self, websocket, data):
        invite_code = data.get("invite_code", "").upper()
        player_name = data.get("player_name", "Guest")
        player_avatar = data.get("player_avatar", "😎")

        # Најди ја сесијата
        session_id = None
        for sid in self.sessions:
            if sid[:8].upper() == invite_code:
                session_id = sid
                break

        if not session_id or session_id not in self.sessions:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Session not found"
            }))
            return

        session_data = self.sessions[session_id]

        if session_data["guest"] is not None:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Session full"
            }))
            return

        # Додај го guest-ot
        session_data["guest"] = websocket
        session_data["guest_info"] = {"name": player_name, "avatar": player_avatar}

        # Извести го host-ot
        await session_data["host"].send(json.dumps({
            "type": "guest_joined",
            "guest_info": session_data["guest_info"]
        }))

        # Извести го guest-ot
        await websocket.send(json.dumps({
            "type": "session_joined",
            "host_info": session_data["host_info"]
        }))

        # Поврзаност
        await asyncio.sleep(0.5)
        connection_msg = {"type": "connection_established"}
        await session_data["host"].send(json.dumps(connection_msg))
        await websocket.send(json.dumps(connection_msg))

        logger.info(f"Connection established for {invite_code}")

    async def handle_game_message(self, websocket, data):
        session_id = data.get("session_id")
        if session_id not in self.sessions:
            return

        session_data = self.sessions[session_id]
        target = None

        if websocket == session_data["host"] and session_data["guest"]:
            target = session_data["guest"]
        elif websocket == session_data["guest"] and session_data["host"]:
            target = session_data["host"]

        if target:
            try:
                await target.send(json.dumps({
                    "type": "game_message",
                    "data": data.get("data")
                }))
            except:
                pass

    async def handle_client(self, websocket, path):
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            await self.unregister_client(websocket)


async def start_http_websocket_server(host="0.0.0.0", port=8765):
    server = HTTPWebSocketServer()
    logger.info(f"Starting HTTP WebSocket server on {host}:{port}")
    logger.info("This server can work with ngrok HTTP tunnels!")

    async with serve(server.handle_client, host, port):
        logger.info("Server running. Use 'ngrok http 8765' to create public tunnel.")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(start_http_websocket_server())