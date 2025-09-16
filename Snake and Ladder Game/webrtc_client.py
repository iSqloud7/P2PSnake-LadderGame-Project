#!/usr/bin/env python3
"""
Поедноставен WebSocket клиент без сложен threading
"""

import asyncio
import json
import websockets
import threading
import queue
import time
from typing import Callable, Optional

WEBRTC_AVAILABLE = True


class WebRTCClient:
    def __init__(self, signaling_server_url="ws://127.0.0.1:8765"):  # Вратено на localhost
        self.signaling_url = signaling_server_url
        self.websocket = None

        self.session_id = None
        self.invite_code = None
        self.is_host = False
        self.connection_state = "disconnected"

        # Callbacks
        self.on_message_received: Optional[Callable] = None
        self.on_connection_state_change: Optional[Callable] = None
        self.on_peer_info_received: Optional[Callable] = None

        # Поедноставен message queue
        self.message_queue = queue.Queue()
        self.running = False

        print(f"Connecting to: {self.signaling_url}")

    def create_session(self, player_name="Host", player_avatar="🙂"):
        """Создај сесија"""
        self.is_host = True
        self.running = True

        def run_host():
            try:
                asyncio.run(self._create_session_async(player_name, player_avatar))
            except Exception as e:
                print(f"Host session error: {e}")
                self.connection_state = "error"
                if self.on_connection_state_change:
                    self.on_connection_state_change("error")

        thread = threading.Thread(target=run_host, daemon=True)
        thread.start()
        return thread

    def join_session(self, invite_code, player_name="Guest", player_avatar="😎"):
        """Приклучи се на сесија"""
        self.is_host = False
        self.running = True

        def run_guest():
            try:
                asyncio.run(self._join_session_async(invite_code, player_name, player_avatar))
            except Exception as e:
                print(f"Guest session error: {e}")
                self.connection_state = "error"
                if self.on_connection_state_change:
                    self.on_connection_state_change("error")

        thread = threading.Thread(target=run_guest, daemon=True)
        thread.start()
        return thread

    async def _create_session_async(self, player_name, player_avatar):
        """Async host сесија"""
        try:
            print("Connecting to signaling server...")
            self.websocket = await websockets.connect(self.signaling_url)

            # Испрати create request
            await self.websocket.send(json.dumps({
                "type": "create_session",
                "player_name": player_name,
                "player_avatar": player_avatar
            }))

            # Слушај пораки
            await self._listen_for_messages()

        except Exception as e:
            print(f"Create session error: {e}")
            self.connection_state = "error"
            if self.on_connection_state_change:
                self.on_connection_state_change("error")
        finally:
            if self.websocket:
                await self.websocket.close()

    async def _join_session_async(self, invite_code, player_name, player_avatar):
        """Async guest сесија"""
        try:
            print("Connecting to signaling server...")
            self.websocket = await websockets.connect(self.signaling_url)

            # Испрати join request
            await self.websocket.send(json.dumps({
                "type": "join_session",
                "invite_code": invite_code.upper(),
                "player_name": player_name,
                "player_avatar": player_avatar
            }))

            # Слушај пораки
            await self._listen_for_messages()

        except Exception as e:
            print(f"Join session error: {e}")
            self.connection_state = "error"
            if self.on_connection_state_change:
                self.on_connection_state_change("error")
        finally:
            if self.websocket:
                await self.websocket.close()

    async def _listen_for_messages(self):
        """Слушај за signaling пораки"""
        try:
            async for message in self.websocket:
                if not self.running:
                    break

                data = json.loads(message)
                message_type = data.get("type")
                print(f"Received: {message_type}")

                if message_type == "session_created":
                    self.session_id = data.get("session_id")
                    self.invite_code = data.get("invite_code")
                    print(f"Session created: {self.invite_code}")

                    self.connection_state = "waiting_for_guest"
                    if self.on_connection_state_change:
                        self.on_connection_state_change("waiting_for_guest")

                elif message_type == "guest_joined":
                    guest_info = data.get("guest_info")
                    print("Guest joined")
                    if self.on_peer_info_received:
                        self.on_peer_info_received(guest_info)

                elif message_type == "session_joined":
                    self.session_id = data.get("session_id")
                    host_info = data.get("host_info")
                    print("Session joined")
                    if self.on_peer_info_received:
                        self.on_peer_info_received(host_info)

                elif message_type == "connection_established":
                    print("Connection established!")
                    self.connection_state = "connected"
                    if self.on_connection_state_change:
                        self.on_connection_state_change("connected")

                elif message_type == "game_message":
                    game_data = data.get("data")
                    print(f"Game message: {game_data.get('type', 'unknown')}")
                    self.message_queue.put(game_data)
                    if self.on_message_received:
                        self.on_message_received(game_data)

                elif message_type == "error":
                    error_msg = data.get("message", "Unknown error")
                    print(f"Server error: {error_msg}")
                    self.connection_state = "error"
                    if self.on_connection_state_change:
                        self.on_connection_state_change("error")
                    break

                elif message_type == "peer_disconnected":
                    print("Peer disconnected")
                    self.connection_state = "peer_disconnected"
                    if self.on_connection_state_change:
                        self.on_connection_state_change("peer_disconnected")
                    break

        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")
        except Exception as e:
            print(f"Listen error: {e}")

    def send_message(self, message_dict):
        """Испрати порака преку нов async call"""
        if not self.websocket or self.connection_state != "connected":
            print("Not ready to send message")
            return False

        def send_async():
            try:
                asyncio.run(self._send_message_async(message_dict))
                return True
            except Exception as e:
                print(f"Send error: {e}")
                return False

        thread = threading.Thread(target=send_async, daemon=True)
        thread.start()
        return True

    async def _send_message_async(self, message_dict):
        """Async испраќање на порaka"""
        if self.websocket and self.connection_state == "connected":
            try:
                # Поврзи се повторно за испраќање
                temp_ws = await websockets.connect(self.signaling_url)
                await temp_ws.send(json.dumps({
                    "type": "game_message",
                    "session_id": self.session_id,
                    "data": message_dict
                }))
                await temp_ws.close()
                print(f"Sent: {message_dict.get('type', 'unknown')}")
            except Exception as e:
                print(f"Send message error: {e}")

    def get_pending_messages(self):
        """Земи pending пораки"""
        messages = []
        try:
            while True:
                message = self.message_queue.get_nowait()
                messages.append(message)
        except queue.Empty:
            pass
        return messages

    def close(self):
        """Едноставно затворање"""
        print("Closing WebSocket client...")
        self.running = False
        self.connection_state = "disconnected"
        # Не се обидуваме да затвориме websocket тука - ќе се затвори автоматски
        print("WebSocket client closed")