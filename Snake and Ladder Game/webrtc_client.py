#!/usr/bin/env python3
"""
WebSocket адаптер што ја замена WebRTC функционалноста
"""

import asyncio
import json
import websockets
import threading
import queue
import time
from typing import Callable, Optional

WEBRTC_AVAILABLE = True  # Симулирај дека WebRTC е достапен


class WebRTCClient:
    def __init__(self, signaling_server_url="ws://127.0.0.1:8765"):
        self.signaling_url = signaling_server_url
        self.websocket = None

        self.session_id = None
        self.invite_code = None
        self.is_host = False
        self.connection_state = "disconnected"

        self.on_message_received: Optional[Callable] = None
        self.on_connection_state_change: Optional[Callable] = None
        self.on_peer_info_received: Optional[Callable] = None

        self.loop = None
        self.thread = None
        self.message_queue = queue.Queue()

        print("🔄 Using WebSocket adapter instead of WebRTC P2P")

    def start_async_thread(self):
        if self.thread and self.thread.is_alive():
            return

        def run_async_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_forever()
            except Exception as e:
                print(f"Error in async loop: {e}")
            finally:
                self.loop.close()

        self.thread = threading.Thread(target=run_async_loop, daemon=True)
        self.thread.start()

        timeout = 10
        start_time = time.time()
        while (not self.loop or not self.loop.is_running()) and (time.time() - start_time < timeout):
            time.sleep(0.1)

    def stop_async_thread(self):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)

    def create_session(self, player_name="Host", player_avatar="🙂"):
        self.is_host = True
        self.start_async_thread()

        future = asyncio.run_coroutine_threadsafe(
            self._create_session_async(player_name, player_avatar),
            self.loop
        )
        return future

    def join_session(self, session_id_or_code, player_name="Guest", player_avatar="😎"):
        self.is_host = False
        self.start_async_thread()

        future = asyncio.run_coroutine_threadsafe(
            self._join_session_async(session_id_or_code, player_name, player_avatar),
            self.loop
        )
        return future

    async def _create_session_async(self, player_name, player_avatar):
        try:
            print(f"Connecting to signaling server: {self.signaling_url}")
            self.websocket = await websockets.connect(self.signaling_url)
            print("Connected to signaling server")

            await self.websocket.send(json.dumps({
                "type": "create_session",
                "player_name": player_name,
                "player_avatar": player_avatar
            }))

            print("Session creation request sent")
            await self._handle_signaling_messages()

        except Exception as e:
            print(f"Error creating session: {e}")
            raise

    async def _join_session_async(self, session_id_or_code, player_name, player_avatar):
        try:
            print(f"Connecting to signaling server: {self.signaling_url}")
            self.websocket = await websockets.connect(self.signaling_url)
            print("Connected to signaling server")

            join_data = {
                "type": "join_session",
                "player_name": player_name,
                "player_avatar": player_avatar
            }

            if len(session_id_or_code) == 8:
                join_data["invite_code"] = session_id_or_code.upper()
                print(f"Joining with invite code: {session_id_or_code}")
            else:
                join_data["session_id"] = session_id_or_code
                print(f"Joining with session ID: {session_id_or_code}")

            await self.websocket.send(json.dumps(join_data))
            await self._handle_signaling_messages()

        except Exception as e:
            print(f"Error joining session: {e}")
            raise

    async def _handle_signaling_messages(self):
        try:
            async for message in self.websocket:
                data = json.loads(message)
                message_type = data.get("type")
                print(f"Received message: {message_type}")

                if message_type == "session_created":
                    self.session_id = data.get("session_id")
                    self.invite_code = data.get("invite_code")
                    print(f"✅ Session created with invite code: {self.invite_code}")

                    if self.on_connection_state_change:
                        self.on_connection_state_change("waiting_for_guest")

                elif message_type == "guest_joined":
                    print("✅ Guest joined")
                    guest_info = data.get("guest_info")

                    if self.on_peer_info_received:
                        self.on_peer_info_received(guest_info)

                elif message_type == "session_joined":
                    self.session_id = data.get("session_id")
                    host_info = data.get("host_info")
                    print(f"✅ Joined session: {self.session_id}")

                    if self.on_peer_info_received:
                        self.on_peer_info_received(host_info)

                elif message_type == "connection_established":
                    print("✅ Connection established via WebSocket!")
                    self.connection_state = "connected"

                    if self.on_connection_state_change:
                        self.on_connection_state_change("connected")

                elif message_type == "game_message":
                    game_data = data.get("data")
                    print(f"📨 Received game message: {game_data.get('type', 'unknown')}")

                    self.message_queue.put(game_data)

                    if self.on_message_received:
                        self.on_message_received(game_data)

                elif message_type == "error":
                    error_msg = data.get("message", "Unknown error")
                    print(f"❌ Error: {error_msg}")
                    raise Exception(f"Signaling error: {error_msg}")

                elif message_type == "peer_disconnected":
                    print("📤 Peer disconnected")
                    if self.on_connection_state_change:
                        self.on_connection_state_change("peer_disconnected")

        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error in signaling: {e}")
            raise

    def send_message(self, message_dict):
        if not self.websocket or self.connection_state != "connected":
            print("⚠️ WebSocket not ready for sending")
            return False

        if self.loop and self.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._send_game_message(message_dict),
                    self.loop
                )
                return True
            except Exception as e:
                print(f"❌ Error sending message: {e}")
                return False
        return False

    async def _send_game_message(self, message_dict):
        if self.websocket:
            await self.websocket.send(json.dumps({
                "type": "game_message",
                "session_id": self.session_id,
                "data": message_dict
            }))
            print(f"📤 Sent game message: {message_dict.get('type', 'unknown')}")

    def get_pending_messages(self):
        messages = []
        try:
            while True:
                message = self.message_queue.get_nowait()
                messages.append(message)
        except queue.Empty:
            pass
        return messages

    def close(self):
        print("🛑 Closing WebSocket client...")

        if self.loop and self.loop.is_running():
            if self.websocket:
                asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)

        self.stop_async_thread()
        self.connection_state = "disconnected"
        print("✅ WebSocket client closed")