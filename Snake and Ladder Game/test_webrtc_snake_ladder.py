#!/usr/bin/env python3
"""
Тест за WebSocket игра без WebRTC - директна комуникација преку signaling сервер
"""

import asyncio
import json
import websockets
import tkinter as tk
from tkinter import messagebox, simpledialog


class WebSocketGameClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Snake & Ladder - WebSocket Mode")
        self.root.geometry("400x300")

        self.websocket = None
        self.session_id = None
        self.is_host = False
        self.peer_info = None

        self.setup_ui()

    def setup_ui(self):
        tk.Label(self.root, text="Snake & Ladder - WebSocket Test",
                 font=("Arial", 16, "bold")).pack(pady=20)

        tk.Button(self.root, text="Host Game", command=self.host_game,
                  font=("Arial", 14), width=15).pack(pady=10)

        tk.Button(self.root, text="Join Game", command=self.join_game,
                  font=("Arial", 14), width=15).pack(pady=10)

        self.status_label = tk.Label(self.root, text="Ready",
                                     font=("Arial", 12))
        self.status_label.pack(pady=20)

    def host_game(self):
        self.is_host = True
        asyncio.run(self.start_host_session())

    def join_game(self):
        invite_code = simpledialog.askstring("Join Game", "Enter invite code:")
        if invite_code:
            self.is_host = False
            asyncio.run(self.join_session(invite_code))

    async def start_host_session(self):
        try:
            self.status_label.config(text="Creating session...")
            self.root.update()

            self.websocket = await websockets.connect("ws://127.0.0.1:8765")

            await self.websocket.send(json.dumps({
                "type": "create_session",
                "player_name": "Host",
                "player_avatar": "🎮"
            }))

            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "session_created":
                    self.session_id = data.get("session_id")
                    invite_code = data.get("invite_code")
                    self.status_label.config(text=f"Waiting for guest...\nInvite code: {invite_code}")
                    self.root.update()

                elif msg_type == "guest_joined":
                    guest_info = data.get("guest_info")
                    self.peer_info = guest_info
                    self.status_label.config(text="Guest joined! Starting game...")
                    self.root.update()

                    # Симулирај успешна WebRTC врска
                    await self.start_game()
                    break

                elif msg_type == "game_message":
                    game_data = data.get("data")
                    print(f"Received game message: {game_data}")

        except Exception as e:
            self.status_label.config(text=f"Error: {e}")

    async def join_session(self, invite_code):
        try:
            self.status_label.config(text="Joining session...")
            self.root.update()

            self.websocket = await websockets.connect("ws://127.0.0.1:8765")

            await self.websocket.send(json.dumps({
                "type": "join_session",
                "invite_code": invite_code.upper(),
                "player_name": "Guest",
                "player_avatar": "😎"
            }))

            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "session_joined":
                    self.session_id = data.get("session_id")
                    host_info = data.get("host_info")
                    self.peer_info = host_info
                    self.status_label.config(text="Connected! Starting game...")
                    self.root.update()

                    await self.start_game()
                    break

                elif msg_type == "error":
                    error_msg = data.get("message")
                    self.status_label.config(text=f"Error: {error_msg}")
                    break

                elif msg_type == "game_message":
                    game_data = data.get("data")
                    print(f"Received game message: {game_data}")

        except Exception as e:
            self.status_label.config(text=f"Error: {e}")

    async def start_game(self):
        """Стартај игра"""
        messagebox.showinfo("Success!",
                            f"Connection established!\n"
                            f"You: {'Host' if self.is_host else 'Guest'}\n"
                            f"Peer: {self.peer_info}")

        # Тест испраќање порака
        await self.send_game_message({"type": "test", "message": "Hello!"})

        self.status_label.config(text="Game ready! Check console for messages.")

    async def send_game_message(self, message_dict):
        """Испрати игра порака"""
        if self.websocket:
            await self.websocket.send(json.dumps({
                "type": "game_message",
                "session_id": self.session_id,
                "data": message_dict
            }))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("Starting WebSocket game test...")
    print("Make sure signaling server is running!")

    client = WebSocketGameClient()
    client.run()