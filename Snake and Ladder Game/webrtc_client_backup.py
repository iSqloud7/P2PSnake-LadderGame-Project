#!/usr/bin/env python3
"""
Едноставна WebRTC клиент верзија што работи со постари aiortc верзии
"""

import asyncio
import json
import logging
from typing import Callable, Optional
import threading
import queue
import time

try:
    from aiortc import RTCPeerConnection, RTCDataChannel, RTCConfiguration, RTCIceServer
    from aiortc import RTCSessionDescription
    import websockets

    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    print("Warning: aiortc not installed. Install with: pip install aiortc")

logger = logging.getLogger(__name__)


class WebRTCClient:
    """Едноставен WebRTC клиент за P2P комуникација"""

    def __init__(self, signaling_server_url="ws://127.0.0.1:8765"):
        if not WEBRTC_AVAILABLE:
            raise ImportError("aiortc library is required for WebRTC functionality")

        self.signaling_url = signaling_server_url
        self.signaling_ws = None

        # Основна WebRTC конфигурација
        ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]

        # Едноставна конфигурација
        self.pc = RTCPeerConnection(configuration=RTCConfiguration(
            iceServers=ice_servers
        ))

        # Data channel за игра пораки
        self.data_channel: Optional[RTCDataChannel] = None

        # Состојби
        self.session_id = None
        self.invite_code = None
        self.is_host = False
        self.connection_state = "disconnected"

        # Callback функции
        self.on_message_received: Optional[Callable] = None
        self.on_connection_state_change: Optional[Callable] = None
        self.on_peer_info_received: Optional[Callable] = None

        # Threading за async операции
        self.loop = None
        self.thread = None
        self.message_queue = queue.Queue()

        # Setup WebRTC event handlers
        self._setup_webrtc_handlers()

    def _setup_webrtc_handlers(self):
        """Постави WebRTC event handlers"""

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = self.pc.connectionState
            print(f"WebRTC Connection state: {state}")

            if state == "connected":
                self.connection_state = "connected"
                print("✅ WebRTC P2P connection established!")
            elif state in ["disconnected", "failed", "closed"]:
                if state == "failed":
                    print("❌ WebRTC connection failed")
                self.connection_state = "disconnected"
            else:
                self.connection_state = "connecting"

            if self.on_connection_state_change:
                try:
                    self.on_connection_state_change(self.connection_state)
                except Exception as e:
                    print(f"Error in connection state callback: {e}")

        @self.pc.on("datachannel")
        def on_datachannel(channel):
            """Прими data channel од remote peer"""
            print(f"Received data channel: {channel.label}")
            self._setup_data_channel(channel)

        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            ice_state = self.pc.iceConnectionState
            print(f"ICE connection state: {ice_state}")

            if ice_state == "connected":
                print("✅ ICE connection established")
            elif ice_state == "failed":
                print("❌ ICE connection failed - NAT/Firewall issues")

    def _setup_data_channel(self, channel: RTCDataChannel):
        """Конфигурирај data channel"""
        self.data_channel = channel

        @channel.on("open")
        def on_open():
            print("✅ Data channel opened - P2P communication ready!")

        @channel.on("message")
        def on_message(message):
            """Прими порака од remote peer"""
            try:
                if isinstance(message, str):
                    data = json.loads(message)
                elif isinstance(message, bytes):
                    data = json.loads(message.decode('utf-8'))
                else:
                    data = {"type": "raw", "data": str(message)}

                print(f"📨 Received P2P message: {data.get('type', 'unknown')}")

                # Стави ја пораката во queue за main thread
                self.message_queue.put(data)

                if self.on_message_received:
                    self.on_message_received(data)

            except Exception as e:
                print(f"Error processing received message: {e}")

        @channel.on("close")
        def on_close():
            print("Data channel closed")

    def start_async_thread(self):
        """Стартај async thread за WebRTC операции"""
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

        # Чекај да се иницијализира loop
        timeout = 10
        start_time = time.time()
        while (not self.loop or not self.loop.is_running()) and (time.time() - start_time < timeout):
            time.sleep(0.1)

    def stop_async_thread(self):
        """Застани async thread"""
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)

    def create_session(self, player_name="Host", player_avatar="🙂"):
        """Создај нова сесија како host"""
        self.is_host = True
        self.start_async_thread()

        # Стартај async операција
        future = asyncio.run_coroutine_threadsafe(
            self._create_session_async(player_name, player_avatar),
            self.loop
        )
        return future

    def join_session(self, session_id_or_code, player_name="Guest", player_avatar="😎"):
        """Приклучи се на постоечка сесија"""
        self.is_host = False
        self.start_async_thread()

        # Стартај async операција
        future = asyncio.run_coroutine_threadsafe(
            self._join_session_async(session_id_or_code, player_name, player_avatar),
            self.loop
        )
        return future

    async def _create_session_async(self, player_name, player_avatar):
        """Async операција за создавање сесија"""
        try:
            print(f"Connecting to signaling server: {self.signaling_url}")

            # Поврзи се на signaling сервер
            self.signaling_ws = await websockets.connect(self.signaling_url)
            print("Connected to signaling server")

            # Создај data channel
            self.data_channel = self.pc.createDataChannel("game", ordered=True)
            self._setup_data_channel(self.data_channel)

            # Испрати барање за создавање сесија
            await self.signaling_ws.send(json.dumps({
                "type": "create_session",
                "player_name": player_name,
                "player_avatar": player_avatar
            }))

            print("Session creation request sent")

            # Чекај одговор од signaling сервер
            await self._handle_signaling_messages()

        except Exception as e:
            print(f"Error creating session: {e}")
            raise

    async def _join_session_async(self, session_id_or_code, player_name, player_avatar):
        """Async операција за приклучување на сесија"""
        try:
            print(f"Connecting to signaling server: {self.signaling_url}")

            # Поврзи се на signaling сервер
            self.signaling_ws = await websockets.connect(self.signaling_url)
            print("Connected to signaling server")

            # Одреди дали е session_id или invite_code
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

            await self.signaling_ws.send(json.dumps(join_data))

            # Чекај одговор од signaling сервер
            await self._handle_signaling_messages()

        except Exception as e:
            print(f"Error joining session: {e}")
            raise

    async def _handle_signaling_messages(self):
        """Обработка на signaling пораки"""
        try:
            async for message in self.signaling_ws:
                data = json.loads(message)
                message_type = data.get("type")
                print(f"Received signaling message: {message_type}")

                if message_type == "session_created":
                    self.session_id = data.get("session_id")
                    self.invite_code = data.get("invite_code")
                    print(f"✅ Session created with invite code: {self.invite_code}")

                    if self.on_connection_state_change:
                        self.on_connection_state_change("waiting_for_guest")

                elif message_type == "guest_joined":
                    print("✅ Guest joined - starting WebRTC negotiation")
                    guest_info = data.get("guest_info")

                    if self.on_peer_info_received:
                        self.on_peer_info_received(guest_info)

                    # Host започнува WebRTC connection
                    await self._initiate_webrtc_connection()

                elif message_type == "session_joined":
                    self.session_id = data.get("session_id")
                    host_info = data.get("host_info")
                    print(f"✅ Joined session: {self.session_id}")

                    if self.on_peer_info_received:
                        self.on_peer_info_received(host_info)

                elif message_type == "webrtc_offer":
                    print("📨 Received WebRTC offer - creating answer")
                    offer_data = data.get("offer")
                    await self._handle_webrtc_offer(offer_data)

                elif message_type == "webrtc_answer":
                    print("📨 Received WebRTC answer - completing connection")
                    answer_data = data.get("answer")
                    await self._handle_webrtc_answer(answer_data)

                elif message_type == "webrtc_ice_candidate":
                    candidate_data = data.get("candidate")
                    await self._handle_ice_candidate(candidate_data)

                elif message_type == "error":
                    error_msg = data.get("message", "Unknown error")
                    print(f"❌ Signaling error: {error_msg}")
                    raise Exception(f"Signaling error: {error_msg}")

                elif message_type == "peer_disconnected":
                    print("📤 Peer disconnected")
                    if self.on_connection_state_change:
                        self.on_connection_state_change("peer_disconnected")

        except websockets.exceptions.ConnectionClosed:
            print("Signaling connection closed")
        except Exception as e:
            print(f"Error in signaling: {e}")
            raise

    async def _initiate_webrtc_connection(self):
        """Host го започнува WebRTC connection процесот"""
        try:
            print("🔄 Creating WebRTC offer...")

            # Создај offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)

            print("📤 Sending WebRTC offer...")

            # Испрати offer преку signaling
            await self.signaling_ws.send(json.dumps({
                "type": "webrtc_offer",
                "session_id": self.session_id,
                "offer": {
                    "type": offer.type,
                    "sdp": offer.sdp
                }
            }))

            if self.on_connection_state_change:
                self.on_connection_state_change("connecting")

        except Exception as e:
            print(f"❌ Error creating WebRTC offer: {e}")
            raise

    async def _handle_webrtc_offer(self, offer_data):
        """Guest го обработува offer и создава answer"""
        try:
            print("🔄 Processing WebRTC offer...")

            # Постави remote description
            offer = RTCSessionDescription(sdp=offer_data["sdp"], type=offer_data["type"])
            await self.pc.setRemoteDescription(offer)

            # Создај answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)

            print("📤 Sending WebRTC answer...")

            # Испрати answer преку signaling
            await self.signaling_ws.send(json.dumps({
                "type": "webrtc_answer",
                "session_id": self.session_id,
                "answer": {
                    "type": answer.type,
                    "sdp": answer.sdp
                }
            }))

            if self.on_connection_state_change:
                self.on_connection_state_change("connecting")

        except Exception as e:
            print(f"❌ Error handling WebRTC offer: {e}")
            raise

    async def _handle_webrtc_answer(self, answer_data):
        """Host го обработува answer"""
        try:
            print("🔄 Processing WebRTC answer...")

            answer = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
            await self.pc.setRemoteDescription(answer)

            print("✅ WebRTC negotiation completed - waiting for ICE connection")

        except Exception as e:
            print(f"❌ Error handling WebRTC answer: {e}")
            raise

    async def _handle_ice_candidate(self, candidate_data):
        """Обработка на ICE кандидати"""
        try:
            from aiortc import RTCIceCandidate

            candidate = RTCIceCandidate(
                candidate=candidate_data["candidate"],
                sdpMid=candidate_data["sdpMid"],
                sdpMLineIndex=candidate_data["sdpMLineIndex"]
            )

            await self.pc.addIceCandidate(candidate)
            print("Processed ICE candidate")

        except Exception as e:
            print(f"Error handling ICE candidate: {e}")

    def send_message(self, message_dict):
        """Испрати порака преку P2P data channel"""
        if not self.data_channel or self.data_channel.readyState != "open":
            print("⚠️ Data channel not ready for sending")
            return False

        try:
            message_json = json.dumps(message_dict)
            self.data_channel.send(message_json)
            print(f"📤 Sent P2P message: {message_dict.get('type', 'unknown')}")
            return True
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return False

    def get_pending_messages(self):
        """Врати ги сите pending пораки од queue"""
        messages = []
        try:
            while True:
                message = self.message_queue.get_nowait()
                messages.append(message)
        except queue.Empty:
            pass
        return messages

    def close(self):
        """Затвори ги сите врски"""
        print("🛑 Closing WebRTC client...")

        if self.loop and self.loop.is_running():
            # Затвори WebRTC connection
            asyncio.run_coroutine_threadsafe(self.pc.close(), self.loop)

            # Затвори signaling connection
            if self.signaling_ws:
                asyncio.run_coroutine_threadsafe(self.signaling_ws.close(), self.loop)

        self.stop_async_thread()
        self.connection_state = "disconnected"
        print("✅ WebRTC client closed")


if __name__ == "__main__":
    if WEBRTC_AVAILABLE:
        print("✅ Simple WebRTC client ready for testing")
    else:
        print("❌ Install dependencies: pip install aiortc websockets")