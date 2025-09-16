#!/usr/bin/env python3
"""
Модифицирана верзија на GameClient што користи WebRTC за P2P комуникација
наместо централизиран WebSocket сервер
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import threading
import json
import time
import os
import requests

# Увези го оригиналниот код
from webrtc_snake_ladder_game import P2PSnakeLadderGame as SnakeLadderGame


SERVER_URL = "http://localhost:8000"

# Увези го WebRTC клиентот
try:
    from webrtc_client import WebRTCClient, WEBRTC_AVAILABLE
except ImportError:
    WEBRTC_AVAILABLE = False


# Увези локални функции (од оригиналниот client.py)
def load_local_profile():
    """Вчитај локален профил од датотека"""
    try:
        if os.path.exists("local_profile.json"):
            with open("local_profile.json", "r") as f:
                return json.load(f)
    except:
        pass
    return {"display_name": "Player", "display_avatar": "🙂", "games_played": 0}


def save_local_profile(profile):
    """Зачувај локален профил"""
    try:
        with open("local_profile.json", "w") as f:
            json.dump(profile, f)
    except:
        pass


class WebRTCGameClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🐍 Snake & Ladder - P2P Edition")
        self.root.configure(bg="#2a9d8f")

        # Локални податоци (без server authentication)
        self.local_profile = load_local_profile()
        self.display_name = self.local_profile.get("display_name", "Player")
        self.display_avatar = self.local_profile.get("display_avatar", "🙂")

        # WebRTC клиент за P2P комуникација
        self.webrtc_client = None
        self.connection_state = "disconnected"
        self.peer_info = None
        self.session_id = None
        self.invite_code = None
        self.is_host = False

        # Game instance
        self.game_instance = None

        if not WEBRTC_AVAILABLE:
            messagebox.showerror(
                "Missing Dependencies",
                "WebRTC functionality requires additional packages:\n\n"
                "pip install aiortc websockets\n\n"
                "Install these packages and restart the application."
            )
            self.root.destroy()
            return

        self.show_login_window()

    def show_login_window(self):
        self.clear_window()
        self.root.geometry("400x300")
        self.root.title("Login / Register")

        tk.Label(self.root, text="🐍 Snake & Ladder Login",
                 font=("Arial", 18, "bold"), bg="#2a9d8f", fg="white").pack(pady=20)

        tk.Label(self.root, text="Username:", bg="#2a9d8f", fg="white").pack()
        username_entry = tk.Entry(self.root, font=("Arial", 12))
        username_entry.pack(pady=5)

        tk.Label(self.root, text="Password:", bg="#2a9d8f", fg="white").pack()
        password_entry = tk.Entry(self.root, font=("Arial", 12), show="*")
        password_entry.pack(pady=5)

        def handle_login():
            u, p = username_entry.get(), password_entry.get()
            try:
                r = requests.post(f"{SERVER_URL}/login", json={"username": u, "password": p})
                if r.status_code == 200:
                    messagebox.showinfo("Success", "Login Successful!")
                    self.display_name = u
                    self.show_main_menu()
                else:
                    messagebox.showerror("Error", r.json().get("detail", "Login failed"))
            except Exception as e:
                messagebox.showerror("Error", f"Server not reachable: {e}")

        def handle_register():
            u, p = username_entry.get(), password_entry.get()
            try:
                r = requests.post(f"{SERVER_URL}/register", json={"username": u, "password": p})
                if r.status_code == 200:
                    messagebox.showinfo("Success", "Registered successfully! Now login.")
                else:
                    messagebox.showerror("Error", r.json().get("detail", "Registration failed"))
            except Exception as e:
                messagebox.showerror("Error", f"Server not reachable: {e}")

        tk.Button(self.root, text="Login", command=handle_login,
                  font=("Arial", 14), bg="#27ae60", fg="white").pack(pady=10)

        tk.Button(self.root, text="Register", command=handle_register,
                  font=("Arial", 14), bg="#2980b9", fg="white").pack(pady=5)

    def update_display_profile(self, name=None, avatar=None):
        """Ажурирај display профил"""
        if name:
            self.display_name = name
            self.local_profile["display_name"] = name
        if avatar:
            self.display_avatar = avatar
            self.local_profile["display_avatar"] = avatar
        save_local_profile(self.local_profile)

    # ---------- UI Methods ----------
    def clear_window(self):
        """Исчисти ги сите елементи од прозорецот"""
        for widget in self.root.winfo_children():
            widget.destroy()

    def show_main_menu(self):
        """Прикажи главно мени"""
        self.clear_window()
        self.root.geometry("600x700")

        # Header
        header_frame = tk.Frame(self.root, bg="#34495e", height=120)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="🐍 Snake & Ladder", font=("Arial", 24, "bold"),
                 bg="#34495e", fg="#ecf0f1").pack(pady=10)

        tk.Label(header_frame, text="P2P Edition - Direct Connection", font=("Arial", 12),
                 bg="#34495e", fg="#95a5a6").pack()

        tk.Label(header_frame, text=f"Playing as: {self.display_avatar} {self.display_name}",
                 font=("Arial", 14, "bold"), bg="#34495e", fg="#f1c40f").pack(pady=5)

        # Main content
        content_frame = tk.Frame(self.root, bg="#2c3e50", padx=40, pady=30)
        content_frame.pack(expand=True, fill="both")

        tk.Label(content_frame, text="Choose Game Mode", font=("Arial", 18, "bold"),
                 bg="#2c3e50", fg="#ecf0f1").pack(pady=20)

        # Game mode buttons
        tk.Button(content_frame, text="🎮 Play Solo (vs Bot)", font=("Arial", 16, "bold"),
                  command=self.play_solo, bg="#e74c3c", fg="white",
                  padx=25, pady=12, width=25, relief=tk.FLAT).pack(pady=10)

        tk.Button(content_frame, text="🌐 Host P2P Game", font=("Arial", 16, "bold"),
                  command=self.host_p2p_game, bg="#27ae60", fg="white",
                  padx=25, pady=12, width=25, relief=tk.FLAT).pack(pady=10)

        tk.Button(content_frame, text="🔗 Join P2P Game", font=("Arial", 16, "bold"),
                  command=self.join_p2p_game, bg="#3498db", fg="white",
                  padx=25, pady=12, width=25, relief=tk.FLAT).pack(pady=10)

        # Profile button
        tk.Button(content_frame, text="👤 Change Profile", command=self.show_profile_window,
                  font=("Arial", 14), bg="#9b59b6", fg="white",
                  padx=15, pady=8, width=20, relief=tk.FLAT).pack(pady=20)

        # Connection status
        status_color = {"disconnected": "#e74c3c", "connecting": "#f39c12",
                        "connected": "#27ae60"}.get(self.connection_state, "#95a5a6")

        tk.Label(content_frame, text=f"Status: {self.connection_state.title()}",
                 font=("Arial", 12), bg="#2c3e50", fg=status_color).pack(pady=10)

        # Local stats preview
        self.show_local_stats_preview(content_frame)

    def show_local_stats_preview(self, parent):
        """Прикажи краток преглед на локални статистики"""
        try:
            if os.path.exists("local_scores.json"):
                with open("local_scores.json", "r") as f:
                    scores = json.load(f)

                stats_frame = tk.Frame(parent, bg="#34495e", relief=tk.FLAT, bd=2)
                stats_frame.pack(pady=15, padx=20, fill="x")

                tk.Label(stats_frame, text="📊 Local Solo Game Stats",
                         font=("Arial", 14, "bold"), bg="#34495e", fg="#ecf0f1").pack(pady=8)

                stats_text = f"Wins: {scores.get('wins', 0)}  •  Losses: {scores.get('losses', 0)}"
                if scores.get('fastest_win'):
                    stats_text += f"  •  Best: {scores['fastest_win']}s"

                tk.Label(stats_frame, text=stats_text,
                         font=("Arial", 11), bg="#34495e", fg="#27ae60").pack(pady=5)
        except:
            pass

    def show_profile_window(self):
        """Прикажи прозорец за профил"""
        profile_window = tk.Toplevel(self.root)
        profile_window.title("Player Profile")
        profile_window.geometry("500x400")
        profile_window.configure(bg="#2c3e50")

        tk.Label(profile_window, text="🎮 Player Profile", font=("Arial", 18, "bold"),
                 bg="#2c3e50", fg="#ecf0f1").pack(pady=15)

        # Avatar selection
        tk.Label(profile_window, text="Choose Avatar:", font=("Arial", 14, "bold"),
                 bg="#2c3e50", fg="#bdc3c7").pack(pady=(20, 10))

        avatars = ["🙂", "😎", "🤖", "🐍", "🐱", "🐯", "🐸", "🐧", "🚀", "⚡", "🎮", "🏆"]
        selected_avatar = tk.StringVar(value=self.display_avatar)

        avatar_frame = tk.Frame(profile_window, bg="#2c3e50")
        avatar_frame.pack(pady=10)

        for i, emoji in enumerate(avatars):
            row = i // 4
            col = i % 4
            b = tk.Radiobutton(avatar_frame, text=emoji, variable=selected_avatar, value=emoji,
                               indicatoron=False, font=("Arial", 20), width=2, height=1,
                               relief="raised", selectcolor="#3498db", bg="#ecf0f1",
                               activebackground="#2ecc71")
            b.grid(row=row, column=col, padx=3, pady=3)

        # Name entry
        tk.Label(profile_window, text="Display Name:", font=("Arial", 14, "bold"),
                 bg="#2c3e50", fg="#bdc3c7").pack(pady=(20, 5))

        name_entry = tk.Entry(profile_window, font=("Arial", 12), width=25, relief=tk.FLAT, bd=5)
        name_entry.insert(0, self.display_name)
        name_entry.pack(pady=5, ipady=5)

        def save_profile():
            new_avatar = selected_avatar.get()
            new_name = name_entry.get().strip() or "Player"

            self.update_display_profile(new_name, new_avatar)
            messagebox.showinfo("Profile Updated", f"Profile updated!\nName: {new_name}\nAvatar: {new_avatar}")
            profile_window.destroy()
            self.show_main_menu()

        tk.Button(profile_window, text="💾 Save Profile", command=save_profile,
                  font=("Arial", 14, "bold"), bg="#27ae60", fg="white",
                  padx=25, pady=10, relief=tk.FLAT).pack(pady=25)

    # ---------- Game Modes ----------
    def play_solo(self):
        """Започни solo игра против бот"""
        self.local_profile["games_played"] = self.local_profile.get("games_played", 0) + 1
        save_local_profile(self.local_profile)

        self.start_game(multiplayer=False, player_name=self.display_name, player_avatar=self.display_avatar)

    def host_p2p_game(self):
        """Host P2P игра"""
        if self.webrtc_client:
            messagebox.showwarning("Already Connected", "Please disconnect from current session first.")
            return

        self.is_host = True
        self.connection_state = "connecting"

        # Создај WebRTC клиент
        self.webrtc_client = WebRTCClient()
        self.webrtc_client.on_connection_state_change = self.on_connection_state_change
        self.webrtc_client.on_message_received = self.on_p2p_message_received
        self.webrtc_client.on_peer_info_received = self.on_peer_info_received

        try:
            # Стартај сесија во background
            future = self.webrtc_client.create_session(self.display_name, self.display_avatar)

            # Покажи waiting прозорец
            self.show_waiting_window("Creating session...")

            # Периодично провери статус
            self.root.after(1000, self.check_session_status)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create session: {e}")
            self.cleanup_webrtc()

    def join_p2p_game(self):
        """Приклучи се на P2P игра"""
        if self.webrtc_client:
            messagebox.showwarning("Already Connected", "Please disconnect from current session first.")
            return

        # Прашај за invite код
        invite_code = simpledialog.askstring("Join Game", "Enter invite code (8 characters):")
        if not invite_code or len(invite_code.strip()) != 8:
            messagebox.showerror("Invalid Code", "Please enter a valid 8-character invite code.")
            return

        self.is_host = False
        self.connection_state = "connecting"

        # Создај WebRTC клиент
        self.webrtc_client = WebRTCClient()
        self.webrtc_client.on_connection_state_change = self.on_connection_state_change
        self.webrtc_client.on_message_received = self.on_p2p_message_received
        self.webrtc_client.on_peer_info_received = self.on_peer_info_received

        try:
            # Приклучи се на сесија
            future = self.webrtc_client.join_session(invite_code.strip(), self.display_name, self.display_avatar)

            # Покажи waiting прозорец
            self.show_waiting_window(f"Joining session {invite_code.upper()}...")

            # Периодично провери статус
            self.root.after(1000, self.check_session_status)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to join session: {e}")
            self.cleanup_webrtc()

    def show_waiting_window(self, message):
        """Покажи прозорец за чекање"""
        self.waiting_window = tk.Toplevel(self.root)
        self.waiting_window.title("Connecting...")
        self.waiting_window.geometry("400x200")
        self.waiting_window.configure(bg="#2c3e50")
        self.waiting_window.transient(self.root)
        self.waiting_window.grab_set()

        tk.Label(self.waiting_window, text="🌐 Connecting to Peer", font=("Arial", 16, "bold"),
                 bg="#2c3e50", fg="#ecf0f1").pack(pady=20)

        self.waiting_label = tk.Label(self.waiting_window, text=message, font=("Arial", 12),
                                      bg="#2c3e50", fg="#bdc3c7", wraplength=350)
        self.waiting_label.pack(pady=10)

        tk.Button(self.waiting_window, text="Cancel", command=self.cancel_connection,
                  font=("Arial", 12), bg="#e74c3c", fg="white", padx=15, pady=5, relief=tk.FLAT).pack(pady=20)

    def cancel_connection(self):
        """Откажи го поврзувањето"""
        self.cleanup_webrtc()
        if hasattr(self, 'waiting_window'):
            self.waiting_window.destroy()
        self.show_main_menu()

    def check_session_status(self):
        """Периодично провери го статусот на сесијата"""
        if not self.webrtc_client:
            return

        # Ако сме host и чекаме guest
        if self.is_host and self.connection_state == "waiting_for_guest":
            if hasattr(self, 'waiting_window'):
                self.waiting_label.config(
                    text=f"Session created! Share invite code: {self.invite_code}\nWaiting for player to join...")

        # Ако сме connected, започни игра
        elif self.connection_state == "connected":
            if hasattr(self, 'waiting_window'):
                self.waiting_window.destroy()
            self.start_p2p_game()
            return

        # Ако има грешка
        elif self.connection_state == "error":
            if hasattr(self, 'waiting_window'):
                self.waiting_window.destroy()
            messagebox.showerror("Connection Failed", "Failed to establish P2P connection.")
            self.cleanup_webrtc()
            self.show_main_menu()
            return

        # Продолжи да проверуваш
        self.root.after(1000, self.check_session_status)

    # ---------- WebRTC Event Handlers ----------
    def on_connection_state_change(self, state):
        """Обработка на промена на connection статус"""
        self.connection_state = state

        if state == "waiting_for_guest" and self.is_host:
            # Зачувај го invite code од WebRTC клиентот
            self.invite_code = getattr(self.webrtc_client, 'invite_code', 'Unknown')

        elif state == "peer_disconnected":
            messagebox.showinfo("Peer Disconnected", "The other player has disconnected.")
            self.cleanup_webrtc()
            self.show_main_menu()

    def on_p2p_message_received(self, message):
        """Обработка на P2P пораки"""
        # Проследи ги пораките во игра инстанцата
        if self.game_instance and hasattr(self.game_instance, 'on_ws_message'):
            self.game_instance.on_ws_message(json.dumps(message))

    def on_peer_info_received(self, peer_info):
        """Кога примиме информации за другиот играч"""
        self.peer_info = peer_info
        print(f"Peer info received: {peer_info}")

    # ---------- Game Management ----------
    def start_p2p_game(self):
        """Започни P2P игра"""
        if not self.peer_info:
            messagebox.showerror("Error", "Peer information not available")
            return

        # Подготви имиња и аватари
        if self.is_host:
            player_names = [self.display_name, self.peer_info.get('name', 'Guest')]
            player_avatars = [self.display_avatar, self.peer_info.get('avatar', '😎')]
        else:
            player_names = [self.peer_info.get('name', 'Host'), self.display_name]
            player_avatars = [self.peer_info.get('avatar', '🙂'), self.display_avatar]

        # Стартај игра со P2P комуникација
        self.start_game(multiplayer=True, player_names=player_names, player_avatars=player_avatars)

    def start_game(self, multiplayer=False, player_names=None, player_avatars=None, player_name=None,
                   player_avatar=None):
        """Започни игра"""
        # НЕ ја скриј главната страна сеуште - само промени големина
        self.root.iconify()  # Минимизирај наместо withdraw

        game_window = tk.Toplevel(self.root)
        game_window.title("Snake & Ladder Game")

        # Обезбеди се дека прозорецот е visible
        game_window.lift()
        game_window.focus_force()

        # Подготви имиња и аватари
        if not multiplayer:
            # Singleplayer vs bot
            names = [player_name or self.display_name, "Bot"]
            avatars = [player_avatar or self.display_avatar, "🤖"]
        else:
            # P2P multiplayer
            names = player_names or [self.display_name, "Peer"]
            avatars = player_avatars or [self.display_avatar, "😎"]

        # Создај игра инстанца со P2P WebSocket замена
        try:
            self.game_instance = SnakeLadderGame(
                game_window,
                player_names=names,
                player_avatars=avatars,
                p2p_connection=P2PWebSocketAdapter(self.webrtc_client) if multiplayer else None,
                singleplayer=not multiplayer,
                is_host=self.is_host if multiplayer else True,
                on_game_end=self.on_game_end
            )
        except Exception as e:
            print(f"Error creating game instance: {e}")
            messagebox.showerror("Game Error", f"Failed to create game: {e}")
            self.root.deiconify()

    def on_game_end(self, winner_idx):
        """Кога играта завршува"""
        self.root.deiconify()  # Покажи главен прозорец
        self.show_main_menu()

    def cleanup_webrtc(self):
        """Исчисти WebRTC ресурси"""
        if self.webrtc_client:
            self.webrtc_client.close()
            self.webrtc_client = None
        self.connection_state = "disconnected"
        self.peer_info = None
        self.session_id = None
        self.invite_code = None

    def run(self):
        """Стартај апликација"""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        finally:
            self.cleanup_webrtc()

    def on_closing(self):
        """При затварање на апликацијата"""
        self.cleanup_webrtc()
        self.root.destroy()


# ---------- P2P WebSocket адаптер ----------
class P2PWebSocketAdapter:
    """Адаптер што ја замена WebSocket функционалноста со P2P комуникација"""

    def __init__(self, webrtc_client):
        self.webrtc_client = webrtc_client

    def send_message(self, message_dict):
        """Испрати порака (API за P2P комуникација)"""
        if self.webrtc_client:
            try:
                return self.webrtc_client.send_message(message_dict)
            except:
                return False
        return False

    def get_pending_messages(self):
        """Земи pending пораки"""
        if self.webrtc_client and hasattr(self.webrtc_client, 'get_pending_messages'):
            return self.webrtc_client.get_pending_messages()
        return []

    def send(self, message):
        """Испрати порака (симулира WebSocket.send)"""
        if self.webrtc_client:
            try:
                data = json.loads(message)
                return self.webrtc_client.send_message(data)
            except:
                return False
        return False

    def close(self):
        """Затвори врска (симулира WebSocket.close)"""
        if self.webrtc_client:
            self.webrtc_client.close()


if __name__ == "__main__":
    if not WEBRTC_AVAILABLE:
        print("Error: Missing dependencies. Install with:")
        print("pip install aiortc websockets")
        exit(1)

    client = WebRTCGameClient()
    client.run()
