#!/usr/bin/env python3
"""
Enhanced Signaling сервер со подобра синхронизација
"""

import asyncio
import websockets
import json
import logging
from typing import Dict, Set
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedSignalingServer:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, websockets.WebSocketServerProtocol]] = {}
        self.all_clients: Set[websockets.WebSocketServerProtocol] = set()

    async def register_client(self, websocket: websockets.WebSocketServerProtocol):
        self.all_clients.add(websocket)
        logger.info(f"Client {websocket.remote_address} connected. Total clients: {len(self.all_clients)}")

    async def unregister_client(self, websocket: websockets.WebSocketServerProtocol):
        if websocket in self.all_clients:
            self.all_clients.remove(websocket)

        sessions_to_remove = []
        for session_id, session_data in self.sessions.items():
            if websocket in session_data.values():
                sessions_to_remove.append(session_id)
                # Извести го другиот клиент дека peer се дисконектирал
                for role, client in session_data.items():
                    if client != websocket and client in self.all_clients:
                        try:
                            await client.send(json.dumps({
                                "type": "peer_disconnected",
                                "session_id": session_id
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            pass

        for session_id in sessions_to_remove:
            del self.sessions[session_id]

        logger.info(f"Client {websocket.remote_address} disconnected. Remaining clients: {len(self.all_clients)}")

    async def handle_message(self, websocket: websockets.WebSocketServerProtocol, message: str):
        try:
            data = json.loads(message)
            message_type = data.get("type")
            logger.info(f"Handling message type: {message_type} from {websocket.remote_address}")

            if message_type == "create_session":
                await self.handle_create_session(websocket, data)
            elif message_type == "join_session":
                await self.handle_join_session(websocket, data)
            elif message_type == "game_message":
                await self.handle_game_message(websocket, data)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received from {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def handle_create_session(self, websocket: websockets.WebSocketServerProtocol, data: dict):
        session_id = str(uuid.uuid4())
        player_name = data.get("player_name", "Host")
        player_avatar = data.get("player_avatar", "🙂")

        self.sessions[session_id] = {
            "host": websocket,
            "guest": None,
            "host_info": {
                "name": player_name,
                "avatar": player_avatar
            },
            "guest_info": None
        }

        invite_code = session_id[:8].upper()

        response = {
            "type": "session_created",
            "session_id": session_id,
            "invite_code": invite_code,
            "player_role": "host"
        }

        await websocket.send(json.dumps(response))
        logger.info(f"Session {session_id} created with invite code {invite_code}")

    async def handle_join_session(self, websocket: websockets.WebSocketServerProtocol, data: dict):
        session_id = data.get("session_id")
        invite_code = data.get("invite_code")
        player_name = data.get("player_name", "Guest")
        player_avatar = data.get("player_avatar", "😎")

        # Ако е предоставен invite код, најди ја сесијата
        if invite_code and not session_id:
            for sid, session_data in self.sessions.items():
                if sid[:8].upper() == invite_code.upper():
                    session_id = sid
                    break

        if not session_id or session_id not in self.sessions:
            error_response = {
                "type": "error",
                "message": "Session not found"
            }
            await websocket.send(json.dumps(error_response))
            logger.warning(f"Session not found for invite code/ID: {invite_code or session_id}")
            return

        session_data = self.sessions[session_id]

        if session_data["guest"] is not None:
            error_response = {
                "type": "error",
                "message": "Session is full"
            }
            await websocket.send(json.dumps(error_response))
            logger.warning(f"Session {session_id} is already full")
            return

        # Додај го guest-от
        session_data["guest"] = websocket
        session_data["guest_info"] = {
            "name": player_name,
            "avatar": player_avatar
        }

        host_socket = session_data["host"]

        # Извести го host-от дека guest се приклучил
        await host_socket.send(json.dumps({
            "type": "guest_joined",
            "session_id": session_id,
            "guest_info": session_data["guest_info"]
        }))

        # Извesti го guest-от дека успешно се приклучил
        await websocket.send(json.dumps({
            "type": "session_joined",
            "session_id": session_id,
            "player_role": "guest",
            "host_info": session_data["host_info"]
        }))

        logger.info(f"Guest {websocket.remote_address} joined session {session_id}")

        # Чекај малку и потоа извести за поврзаност
        await asyncio.sleep(0.5)

        # Извести за успешна поврзаност
        connection_msg = {
            "type": "connection_established",
            "session_id": session_id
        }

        try:
            await host_socket.send(json.dumps(connection_msg))
            await websocket.send(json.dumps(connection_msg))
            logger.info(f"Connection established for session {session_id}")
        except websockets.exceptions.ConnectionClosed:
            logger.error(f"Connection closed while establishing session {session_id}")

    async def handle_game_message(self, websocket: websockets.WebSocketServerProtocol, data: dict):
        session_id = data.get("session_id")
        game_data = data.get("data")

        if session_id not in self.sessions:
            logger.warning(f"Game message for non-existent session: {session_id}")
            return

        session_data = self.sessions[session_id]

        # Определи кој е target клиент
        target = None
        if websocket == session_data["host"] and session_data["guest"]:
            target = session_data["guest"]
        elif websocket == session_data["guest"] and session_data["host"]:
            target = session_data["host"]

        if target and target in self.all_clients:
            try:
                await target.send(json.dumps({
                    "type": "game_message",
                    "session_id": session_id,
                    "data": game_data
                }))
                logger.debug(f"Relayed game message in session {session_id}")
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"Target client disconnected while relaying message")
        else:
            logger.warning(f"No valid target for game message in session {session_id}")

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {websocket.remote_address} disconnected normally")
        except Exception as e:
            logger.error(f"Error handling client {websocket.remote_address}: {e}")
        finally:
            await self.unregister_client(websocket)


async def start_signaling_server(host="0.0.0.0", port=8765):
    """Стартај signaling сервер"""
    server = EnhancedSignalingServer()
    logger.info(f"Starting signaling server on {host}:{port}")

    try:
        async with websockets.serve(server.handle_client, host, port,
                                    ping_interval=30, ping_timeout=10):
            logger.info("Signaling server is running. Press Ctrl+C to stop.")
            await asyncio.Future()  # run forever
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(start_signaling_server())
    except KeyboardInterrupt:
        print("\nServer stopped by user")