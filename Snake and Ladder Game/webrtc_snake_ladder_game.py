#!/usr/bin/env python3
"""
Исправена P2P Snake & Ladder игра со правилна синхронизација
"""

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw
import random
import os
import math
import time
import json

# Константи
BOARD_SIZE = 640
TILE_SIZE = BOARD_SIZE // 10
BOARD_MARGIN = 40
ASSET_PATH = "snake_ladder_assets/"

SNAKES = {98: 78, 95: 56, 87: 24, 62: 18, 54: 34, 16: 6}
LADDERS = {1: 38, 4: 14, 9: 21, 28: 84, 36: 44, 51: 67, 71: 91, 80: 100}


class P2PSnakeLadderGame:
    """
    P2P верзија со исправена синхронизација
    """

    def __init__(self, root,
                 player_names=None,
                 player_avatars=None,
                 p2p_connection=None,
                 singleplayer=False,
                 is_host=True,
                 on_game_end=None):

        self.root = root
        self.root.title("Snake & Ladder Game - P2P")
        self.root.configure(bg="#2c3e50")

        # P2P комуникација
        self.p2p_connection = p2p_connection
        self.singleplayer = singleplayer
        self.is_host = is_host
        self.on_game_end = on_game_end

        # Статистики
        self.start_time = time.time()
        self.total_moves = [0, 0]

        # Играчи
        self.player_names = player_names or ["Player 1", "Player 2"]
        self.player_avatars = player_avatars or ["🙂", "😎"]

        # Локални статистики
        self.local_score = self.load_local_score()

        # P2P синхронизација
        self.game_state_synced = True
        self.pending_moves = []
        self.message_buffer = []
        self.message_check_interval = 100

        # Игрална логика
        self.positions = [0, 0]
        self.dice_value = 0
        self.current_player = 0  # 0 = host, 1 = guest
        self.movable = False
        self.my_player_index = 0 if self.is_host else 1  # Мој индекс

        # За P2P - чекаме confirmation пред switch_turn
        self.waiting_for_move_confirmation = False

        # Иницијализирај UI прво
        self.setup_ui()
        self.init_game()

        # Стартај периодично процесирање на пораки
        self.process_p2p_messages()

        # Обезбеди се дека прозорецот е visible
        self.root.update()
        self.root.deiconify()
        self.root.lift()

    def setup_ui(self):
        """Setup UI"""
        # Постави минимална големина
        self.root.geometry("1000x800")

        main_frame = tk.Frame(self.root, bg="#2c3e50")
        main_frame.pack(expand=True, fill=tk.BOTH, padx=15, pady=15)

        # Board container
        board_container = tk.Frame(main_frame, bg="#34495e", relief=tk.RAISED, bd=3)
        board_container.pack(side=tk.LEFT, padx=10, anchor="n")

        canvas_width = BOARD_SIZE + BOARD_MARGIN * 2
        canvas_height = BOARD_SIZE + BOARD_MARGIN * 2

        self.canvas = tk.Canvas(board_container, width=canvas_width, height=canvas_height,
                                bg="#2c3e50", highlightbackground="#34495e", highlightthickness=3,
                                relief=tk.RAISED, bd=2)
        self.canvas.pack(padx=8, pady=8)

        # Controls frame
        self.controls_frame = tk.Frame(main_frame, bg="#34495e", width=280, relief=tk.RAISED, bd=3)
        self.controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, anchor="n")
        self.controls_frame.pack_propagate(False)

        self.root.minsize(canvas_width + 320 + 50, canvas_height + 100)

        # Иницијализирај сликите прво
        self.load_images()

        # Потоа цртај ги остатокот
        self.draw_board()
        self.draw_snakes_and_ladders()

    def init_game(self):
        """Иницијализирај игра"""
        self.positions = [0, 0]

        # Создај токени
        self.tokens = [
            self.canvas.create_oval(0, 0, 24, 24, fill='#e74c3c', outline='#c0392b', width=3, tags="player0"),
            self.canvas.create_oval(0, 0, 24, 24, fill='#3498db', outline='#2980b9', width=3, tags="player1")
        ]

        # Етикети
        self.labels = [
            self.canvas.create_text(0, 0, text=f"{self.player_avatars[0]}",
                                    font=("Arial", 16, "bold"), fill="#e74c3c", tags="label0"),
            self.canvas.create_text(0, 0, text=f"{self.player_avatars[1]}",
                                    font=("Arial", 16, "bold"), fill="#3498db", tags="label1")
        ]

        self.dice_value = 0
        self.current_player = 0  # Host винаги започнува
        self.movable = False
        self.waiting_for_move_confirmation = False

        self.setup_controls()
        self.move_token(0)
        self.move_token(1)

        # Bind кликови на токени - само за свој токен
        if not self.singleplayer:
            if self.my_player_index == 0:
                self.canvas.tag_bind("player0", "<Button-1>", lambda e: self.try_move(0))
            else:
                self.canvas.tag_bind("player1", "<Button-1>", lambda e: self.try_move(1))
        else:
            # Во singleplayer мод, bind и двата токени
            self.canvas.tag_bind("player0", "<Button-1>", lambda e: self.try_move(0))
            self.canvas.tag_bind("player1", "<Button-1>", lambda e: self.try_move(1))

        # P2P иницијализација
        if self.p2p_connection:
            self.send_p2p_message({
                "type": "player_ready",
                "player_index": self.my_player_index,
                "name": self.player_names[self.my_player_index],
                "avatar": self.player_avatars[self.my_player_index]
            })

        self.update_turn_status()

    def setup_controls(self):
        """Setup контроли"""
        # Title
        title_frame = tk.Frame(self.controls_frame, bg="#34495e")
        title_frame.pack(pady=15, fill="x")
        tk.Label(title_frame, text="Snake & Ladder", font=("Arial", 18, "bold"),
                 bg="#34495e", fg="#ecf0f1").pack()

        # Players info
        players_frame = tk.Frame(self.controls_frame, bg="#2c3e50", relief=tk.SUNKEN, bd=2)
        players_frame.pack(pady=10, padx=10, fill="x")

        self.player_labels = [
            tk.Label(players_frame, text=f"{self.player_avatars[0]} {self.player_names[0]}",
                     font=("Arial", 12, "bold"), bg="#2c3e50", fg="#e74c3c"),
            tk.Label(players_frame, text=f"{self.player_avatars[1]} {self.player_names[1]}",
                     font=("Arial", 12, "bold"), bg="#2c3e50", fg="#3498db")
        ]

        self.player_labels[0].pack(pady=2)
        tk.Label(players_frame, text="VS", font=("Arial", 10, "bold"),
                 bg="#2c3e50", fg="#bdc3c7").pack()
        self.player_labels[1].pack(pady=2)

        # Dice
        dice_frame = tk.Frame(self.controls_frame, bg="#34495e")
        dice_frame.pack(pady=20)

        self.dice_label = tk.Label(dice_frame, bg="#34495e")
        self.dice_label.pack(pady=10)

        # Buttons
        self.roll_button = tk.Button(dice_frame, text="Roll Dice", command=self.roll_dice,
                                     font=("Arial", 14, "bold"), bg="#27ae60", fg="white",
                                     activebackground="#2ecc71", relief=tk.RAISED, bd=3,
                                     padx=15, pady=8, width=12)
        self.roll_button.pack(pady=5)

        self.reset_button = tk.Button(dice_frame, text="Reset Game", command=self.reset_game,
                                      font=("Arial", 12), bg="#e67e22", fg="white",
                                      activebackground="#f39c12", relief=tk.RAISED, bd=3,
                                      padx=10, pady=5, width=12)
        self.reset_button.pack(pady=5)

        # Status
        self.status_label = tk.Label(self.controls_frame, text="Starting game...",
                                     font=("Arial", 14, "bold"), bg="#34495e", fg="#f1c40f",
                                     wraplength=250, justify="center")
        self.status_label.pack(pady=15)

        # Debug info за P2P
        if not self.singleplayer:
            role_text = "Host (Red)" if self.is_host else "Guest (Blue)"
            tk.Label(self.controls_frame, text=f"You are: {role_text}", font=("Arial", 10),
                     bg="#34495e", fg="#ecf0f1").pack()

        # Локални поени за singleplayer
        if self.singleplayer and self.local_score:
            self.show_local_score()

    def show_local_score(self):
        """Прикажи локални статистики"""
        score_frame = tk.Frame(self.controls_frame, bg="#2c3e50", relief=tk.SUNKEN, bd=2)
        score_frame.pack(pady=10, padx=10, fill="x")

        tk.Label(score_frame, text="Local Statistics", font=("Arial", 12, "bold"),
                 bg="#2c3e50", fg="#95a5a6").pack(pady=5)

        wins = self.local_score.get('wins', 0)
        losses = self.local_score.get('losses', 0)
        fastest = self.local_score.get('fastest_win')

        tk.Label(score_frame, text=f"Wins: {wins}", font=("Arial", "10"),
                 bg="#2c3e50", fg="#27ae60").pack()
        tk.Label(score_frame, text=f"Losses: {losses}", font=("Arial", "10"),
                 bg="#2c3e50", fg="#e74c3c").pack()

        if fastest:
            tk.Label(score_frame, text=f"Best: {fastest}s", font=("Arial", "10"),
                     bg="#2c3e50", fg="#f39c12").pack()

    # ---------- P2P Communication Methods ----------
    def send_p2p_message(self, message_dict):
        """Испрати P2P порака"""
        if self.p2p_connection:
            try:
                print(f"Sending P2P: {message_dict.get('type')}")
                return self.p2p_connection.send_message(message_dict)
            except Exception as e:
                print(f"Error sending P2P message: {e}")
                return False
        return False

    def process_p2p_messages(self):
        """Периодично процесирај P2P пораки"""
        if self.p2p_connection and hasattr(self.p2p_connection, 'get_pending_messages'):
            try:
                messages = self.p2p_connection.get_pending_messages()
                for message in messages:
                    self.handle_p2p_message(message)
            except Exception as e:
                print(f"Error processing P2P messages: {e}")

        # Закажи следно проверување
        self.root.after(self.message_check_interval, self.process_p2p_messages)

    def handle_p2p_message(self, message):
        """Обработка на примени P2P пораки"""
        try:
            message_type = message.get("type")
            print(f"Received P2P: {message_type}")

            if message_type == "player_ready":
                player_index = message.get("player_index")
                name = message.get("name", "Player")
                avatar = message.get("avatar", "😎")
                self.update_player_info(player_index, name, avatar)

            elif message_type == "dice_roll":
                dice_value = int(message.get("value", 1))
                player = int(message.get("player", 0))
                self.handle_remote_dice_roll(player, dice_value)

            elif message_type == "player_move":
                player = int(message.get("player", 0))
                new_position = int(message.get("new_position", 0))
                self.handle_remote_move(player, new_position)

            elif message_type == "move_complete":
                player = int(message.get("player", 0))
                self.handle_move_complete(player)

            elif message_type == "game_sync":
                self.sync_game_state(message.get("state", {}))

            elif message_type == "reset":
                self.reset_game()

        except Exception as e:
            print(f"Error handling P2P message: {e}")

    def handle_remote_dice_roll(self, player, dice_value):
        """Обработка на remote dice roll"""
        if not self.singleplayer and player != self.my_player_index:
            self.dice_value = dice_value
            if 1 <= dice_value <= 6:
                self.dice_label.config(image=self.dice_images[dice_value - 1])

            self.status_label.config(text=f"{self.player_names[player]} rolled {dice_value}")
            print(f"Remote player {player} rolled {dice_value}")

    def handle_remote_move(self, player, new_position):
        """Обработка на remote движење"""
        if not self.singleplayer and player != self.my_player_index:
            print(f"Remote move: Player {player} to position {new_position}")

            # Ажурирај позиција
            self.positions[player] = new_position
            self.move_token(player)

            # Испрати confirmation
            self.send_p2p_message({
                "type": "move_complete",
                "player": player
            })

    def handle_move_complete(self, player):
        """Обработка на завршен потег"""
        if self.waiting_for_move_confirmation and player != self.my_player_index:
            print(f"Move confirmed for player {player}")
            self.waiting_for_move_confirmation = False

            # Провери за победа
            if self.positions[player] >= 100:
                self.handle_victory(player)
            else:
                self.switch_turn()

    def sync_game_state(self, state):
        """Синхронизирај состојба на игра"""
        try:
            if "positions" in state:
                self.positions = state["positions"]
                for i in range(len(self.positions)):
                    self.move_token(i)

            if "current_player" in state:
                self.current_player = state["current_player"]
                self.update_turn_status()

        except Exception as e:
            print(f"Error syncing game state: {e}")

    def update_turn_status(self):
        """Ажурирај статус за ред"""
        if not self.singleplayer:
            if self.current_player == self.my_player_index:
                self.status_label.config(text="Your turn - Roll the dice!")
                self.roll_button.config(state=tk.NORMAL)
            else:
                opponent_name = self.player_names[1 - self.my_player_index]
                self.status_label.config(text=f"Waiting for {opponent_name}")
                self.roll_button.config(state=tk.DISABLED)
        else:
            self.status_label.config(text=f"{self.player_names[self.current_player]}'s turn")

    # ---------- Game Logic Methods ----------
    def roll_dice(self):
        """Фрли коцка"""
        if self.movable or self.waiting_for_move_confirmation:
            self.status_label.config(text="Complete your move first!")
            return

        # Провери дали е твој ред
        if not self.singleplayer and self.current_player != self.my_player_index:
            self.status_label.config(text="Wait for your turn!")
            return

        self.roll_button.config(state=tk.DISABLED)
        self.animate_dice()

    def animate_dice(self, frame=0):
        """Анимација на коцка"""
        if frame < 15:
            value = random.randint(1, 6)
            self.dice_label.config(image=self.dice_images[value - 1])
            self.root.after(80, lambda: self.animate_dice(frame + 1))
        else:
            self.dice_value = random.randint(1, 6)
            self.dice_label.config(image=self.dice_images[self.dice_value - 1])

            # Испрати dice roll до другиот играч
            if not self.singleplayer:
                self.send_p2p_message({
                    "type": "dice_roll",
                    "player": self.current_player,
                    "value": self.dice_value
                })

            # Овозможи движење
            self.movable = True
            self.status_label.config(text=f"You rolled {self.dice_value}. Click your token to move.")

            # Автоматско движење за бот
            if self.singleplayer and self.current_player == 1:
                self.root.after(800, lambda: self.try_move(1))

    def try_move(self, player):
        """Обиди се да се движиш"""
        # Во P2P мод, играчот може да движи само свој токен во свој ред
        if not self.singleplayer:
            if player != self.my_player_index or self.current_player != self.my_player_index:
                self.status_label.config(text="Wait for your turn!")
                return

        if player != self.current_player or not self.movable:
            return

        current_pos = self.positions[player]
        next_pos = current_pos + self.dice_value

        if current_pos == 0:
            next_pos = self.dice_value

        if next_pos > 100:
            self.status_label.config(text="Overshot! Turn passes.")
            self.movable = False
            if not self.singleplayer:
                self.switch_turn()
            else:
                self.switch_turn()
            return

        self.total_moves[player] += 1

        # Започни анимација на движење
        self.animate_token_move(player, current_pos, next_pos)

    def animate_token_move(self, player, start_pos, end_pos, step=0):
        """Анимација на движење на токен"""
        if step < (end_pos - start_pos):
            intermediate_pos = start_pos + step + 1
            self.positions[player] = intermediate_pos
            self.move_token(player)
            self.root.after(100, lambda: self.animate_token_move(player, start_pos, end_pos, step + 1))
        else:
            # Завршена основна анимација, провери за змии/скали
            final_pos = end_pos

            if final_pos in LADDERS:
                self.status_label.config(text=f"{self.player_names[player]} climbed a ladder!")
                ladder_top = LADDERS[final_pos]
                self.root.after(500, lambda: self.animate_special_move(player, final_pos, ladder_top))
                return
            elif final_pos in SNAKES:
                self.status_label.config(text=f"{self.player_names[player]} was bitten by a snake!")
                snake_tail = SNAKES[final_pos]
                self.root.after(500, lambda: self.animate_special_move(player, final_pos, snake_tail))
                return

            self.positions[player] = final_pos
            self.move_token(player)
            self.movable = False

            # Испрати движење до другиот играч
            if not self.singleplayer and player == self.my_player_index:
                self.waiting_for_move_confirmation = True
                self.send_p2p_message({
                    "type": "player_move",
                    "player": player,
                    "new_position": final_pos
                })

            if final_pos >= 100:
                self.handle_victory(player)
            elif self.singleplayer or player == self.my_player_index:
                if not self.waiting_for_move_confirmation:
                    self.switch_turn()

    def animate_special_move(self, player, from_pos, to_pos):
        """Анимација за специјални движења (змии/скали)"""
        self.positions[player] = to_pos
        self.move_token(player)
        self.movable = False

        # Испрати движење до другиот играч
        if not self.singleplayer and player == self.my_player_index:
            self.waiting_for_move_confirmation = True
            self.send_p2p_message({
                "type": "player_move",
                "player": player,
                "new_position": to_pos
            })

        if to_pos >= 100:
            self.handle_victory(player)
        elif self.singleplayer or player == self.my_player_index:
            if not self.waiting_for_move_confirmation:
                self.switch_turn()

    def move_token(self, player):
        """Движење на токен"""
        if self.positions[player] <= 0:
            if player == 0:
                x, y = 15, BOARD_SIZE + BOARD_MARGIN - 40
            else:
                x, y = BOARD_SIZE + BOARD_MARGIN * 2 - 15, BOARD_SIZE + BOARD_MARGIN - 40
        else:
            x, y = self.get_tile_center_coords(self.positions[player])

        if player == 0:
            offset_x, offset_y = -8, -8
        else:
            offset_x, offset_y = 8, 8

        self.canvas.coords(self.tokens[player],
                           x + offset_x - 12, y + offset_y - 12,
                           x + offset_x + 12, y + offset_y + 12)

        if self.positions[player] <= 0:
            label_y = y + offset_y - 30
        else:
            label_y = y + offset_y - 30

        self.canvas.coords(self.labels[player], x + offset_x, label_y)

    def handle_victory(self, player):
        """Обработка на победа"""
        winner_name = self.player_names[player]
        self.status_label.config(text=f"🎉 {winner_name} WINS! 🎉")
        self.roll_button.config(state=tk.DISABLED)

        duration = int(time.time() - self.start_time)

        if self.singleplayer:
            if player == 0:
                self.save_local_score("win", duration)
            else:
                self.save_local_score("loss")

        choice = messagebox.askquestion("Game Over",
                                        f"{winner_name} wins!\nGame duration: {duration}s\nPlay again?",
                                        icon='question')
        if choice == "yes":
            self.reset_game()
            if not self.singleplayer:
                self.send_p2p_message({"type": "reset"})
        else:
            if callable(self.on_game_end):
                self.on_game_end(player)
            self.root.quit()

    def switch_turn(self):
        """Смени ред"""
        self.current_player = 1 - self.current_player
        self.update_turn_status()

        # Синхронизирај состојба во P2P мод
        if not self.singleplayer:
            self.send_p2p_message({
                "type": "game_sync",
                "state": {
                    "positions": self.positions,
                    "current_player": self.current_player
                }
            })

        if self.singleplayer and self.current_player == 1:
            self.root.after(1000, self.roll_dice)

    def reset_game(self):
        """Resetiraj игра"""
        self.positions = [0, 0]
        self.move_token(0)
        self.move_token(1)
        self.current_player = 0
        self.movable = False
        self.waiting_for_move_confirmation = False
        self.update_turn_status()
        self.dice_label.config(image='')
        self.total_moves = [0, 0]
        self.start_time = time.time()

    def update_player_info(self, player_idx, name, avatar):
        """Ажурирај информации за играч"""
        if 0 <= player_idx < len(self.player_names):
            self.player_names[player_idx] = name
            self.player_avatars[player_idx] = avatar

            if hasattr(self, 'player_labels') and player_idx < len(self.player_labels):
                color = "#e74c3c" if player_idx == 0 else "#3498db"
                self.player_labels[player_idx].config(text=f"{avatar} {name}", fg=color)

            if player_idx < len(self.labels):
                self.canvas.itemconfig(self.labels[player_idx], text=avatar)

    # ---------- Local Score Methods ----------
    def load_local_score(self):
        """Вчитај локални поени"""
        try:
            if os.path.exists("local_scores.json"):
                with open("local_scores.json", "r") as f:
                    return json.load(f)
        except:
            pass
        return {"wins": 0, "losses": 0, "fastest_win": None}

    def save_local_score(self, result, duration=None):
        """Зачувај локални поени"""
        if not self.singleplayer:
            return

        if result == "win":
            self.local_score["wins"] += 1
            if duration and (not self.local_score["fastest_win"] or duration < self.local_score["fastest_win"]):
                self.local_score["fastest_win"] = duration
        elif result == "loss":
            self.local_score["losses"] += 1

        try:
            with open("local_scores.json", "w") as f:
                json.dump(self.local_score, f)
        except:
            pass

    # ---------- Image and Board Methods ----------
    def create_dice_image(self, value, size=70):
        """Создај слика на коцка"""
        img = Image.new('RGB', (size, size), '#ecf0f1')
        draw = ImageDraw.Draw(img)
        dot_radius = size // 12
        center = size // 2
        offset = size // 4

        # Рамка на коцката
        draw.rectangle([2, 2, size - 3, size - 3], outline='#34495e', width=3, fill='#ecf0f1')

        # Точки врз основа на вредност
        dots = {
            1: [(center, center)],
            2: [(center - offset, center - offset), (center + offset, center + offset)],
            3: [(center - offset, center - offset), (center, center), (center + offset, center + offset)],
            4: [(center - offset, center - offset), (center + offset, center - offset),
                (center - offset, center + offset), (center + offset, center + offset)],
            5: [(center - offset, center - offset), (center + offset, center - offset),
                (center - offset, center + offset), (center + offset, center + offset), (center, center)],
            6: [(center - offset, center - offset), (center + offset, center - offset),
                (center - offset, center), (center + offset, center),
                (center - offset, center + offset), (center + offset, center + offset)]
        }

        for x, y in dots[value]:
            draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill='#e74c3c')
        return ImageTk.PhotoImage(img)

    def load_images(self):
        """Вчитај слики"""
        self.dice_images = [self.create_dice_image(i) for i in range(1, 7)]

        try:
            snake_path = os.path.join(ASSET_PATH, "snake_big.png")
            ladder_path = os.path.join(ASSET_PATH, "ladder_big.png")

            if os.path.exists(snake_path):
                self.base_snake_img = Image.open(snake_path).convert("RGBA")
            else:
                self.base_snake_img = self.create_snake_image()

            if os.path.exists(ladder_path):
                self.base_ladder_img = Image.open(ladder_path).convert("RGBA")
            else:
                self.base_ladder_img = self.create_ladder_image()

        except Exception:
            self.base_snake_img = self.create_snake_image()
            self.base_ladder_img = self.create_ladder_image()

    def create_snake_image(self):
        """Создади слика на змија"""
        img = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([10, 20, 70, 60], fill='#e74c3c', outline='#c0392b', width=3)
        draw.ellipse([50, 10, 75, 35], fill='#c0392b', outline='#8b0000', width=2)
        draw.ellipse([58, 16, 62, 20], fill='white')
        draw.ellipse([68, 16, 72, 20], fill='white')
        draw.ellipse([59, 17, 61, 19], fill='black')
        draw.ellipse([69, 17, 71, 19], fill='black')
        return img

    def create_ladder_image(self):
        """Создади слика на скала"""
        img = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([25, 5, 30, 75], fill='#8B4513', outline='#654321', width=1)
        draw.rectangle([50, 5, 55, 75], fill='#8B4513', outline='#654321', width=1)
        for i in range(6):
            y = 10 + i * 11
            draw.rectangle([25, y, 55, y + 3], fill='#A0522D', outline='#654321', width=1)
        return img

    def draw_board(self):
        """Цртај табла"""
        colors = ['#3498db', '#5dade2', '#85c1e9', '#aed6f1', '#d6eaf8', '#ebf5fb']

        for row in range(10):
            for col in range(10):
                x1 = col * TILE_SIZE + BOARD_MARGIN
                y1 = (9 - row) * TILE_SIZE + BOARD_MARGIN
                x2 = x1 + TILE_SIZE
                y2 = y1 + TILE_SIZE

                if row % 2 == 0:
                    index = row * 10 + col + 1
                else:
                    index = row * 10 + (9 - col) + 1

                color_index = (row + col) % len(colors)
                color = colors[color_index]

                if index == 1:
                    color = '#27ae60'
                elif index == 100:
                    color = '#f1c40f'
                elif index in SNAKES:
                    color = '#e74c3c'
                elif index in LADDERS:
                    color = '#2ecc71'

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline='#2c3e50', width=2)
                self.canvas.create_text(x1 + TILE_SIZE // 2, y1 + TILE_SIZE // 2,
                                        text=str(index), font=("Arial", 12, "bold"), fill="#2c3e50")

    def get_tile_center_coords(self, pos):
        """Врати координати за позиција"""
        if pos <= 0:
            x = 15
            y = BOARD_SIZE + BOARD_MARGIN - 40
            return x, y

        if pos > 100:
            pos = 100

        pos -= 1
        row = pos // 10

        if row % 2 == 0:
            col = pos % 10
        else:
            col = 9 - (pos % 10)

        x = col * TILE_SIZE + TILE_SIZE // 2 + BOARD_MARGIN
        y = BOARD_SIZE - (row * TILE_SIZE + TILE_SIZE // 2) + BOARD_MARGIN
        return x, y

    def draw_snakes_and_ladders(self):
        """Цртај змии и скали"""
        self.snake_photo_images = []
        self.ladder_photo_images = []

        for start_pos, end_pos in SNAKES.items():
            self._draw_snake(start_pos, end_pos)

        for start_pos, end_pos in LADDERS.items():
            self._draw_ladder(start_pos, end_pos)

        self.canvas.tag_raise("player0")
        self.canvas.tag_raise("player1")
        self.canvas.tag_raise("label0")
        self.canvas.tag_raise("label1")

    def _draw_snake(self, start_pos, end_pos):
        """Цртај змија"""
        start_x, start_y = self.get_tile_center_coords(start_pos)
        end_x, end_y = self.get_tile_center_coords(end_pos)

        self.canvas.create_line(start_x, start_y, end_x, end_y,
                                fill='#c0392b', width=8, smooth=True,
                                capstyle=tk.ROUND, arrow=tk.LAST, arrowshape=(16, 20, 6))

        try:
            resized_snake = self.base_snake_img.resize((40, 40), Image.Resampling.LANCZOS)
            snake_photo = ImageTk.PhotoImage(resized_snake)
            self.snake_photo_images.append(snake_photo)
            self.canvas.create_image(end_x, end_y, image=snake_photo)
        except Exception:
            self.canvas.create_oval(end_x - 8, end_y - 8, end_x + 8, end_y + 8,
                                    fill='#e74c3c', outline='#c0392b', width=2)

    def _draw_ladder(self, start_pos, end_pos):
        """Цртај скала"""
        start_x, start_y = self.get_tile_center_coords(start_pos)
        end_x, end_y = self.get_tile_center_coords(end_pos)

        offset = 8
        self.canvas.create_line(start_x - offset, start_y, end_x - offset, end_y,
                                fill='#27ae60', width=4, capstyle=tk.ROUND)
        self.canvas.create_line(start_x + offset, start_y, end_x + offset, end_y,
                                fill='#27ae60', width=4, capstyle=tk.ROUND)

        steps = 5
        for i in range(1, steps):
            step_x1 = start_x + (end_x - start_x) * i / steps - offset
            step_y1 = start_y + (end_y - start_y) * i / steps
            step_x2 = start_x + (end_x - start_x) * i / steps + offset
            step_y2 = start_y + (end_y - start_y) * i / steps
            self.canvas.create_line(step_x1, step_y1, step_x2, step_y2, fill='#2ecc71', width=3)

        try:
            angle = math.atan2(end_y - start_y, end_x - start_x)
            angle_deg = math.degrees(angle)
            rotated_ladder = self.base_ladder_img.rotate(-angle_deg, expand=True)
            resized_ladder = rotated_ladder.resize((50, 50), Image.Resampling.LANCZOS)
            ladder_photo = ImageTk.PhotoImage(resized_ladder)
            self.ladder_photo_images.append(ladder_photo)
            mid_x = (start_x + end_x) // 2
            mid_y = (start_y + end_y) // 2
            self.canvas.create_image(mid_x, mid_y, image=ladder_photo)
        except Exception:
            pass

    def on_ws_message(self, message):
        """Compatibility метод за интеграција со постоечкиот код"""
        try:
            data = json.loads(message)
            self.handle_p2p_message(data)
        except json.JSONDecodeError:
            print(f"Invalid JSON message: {message}")


# Alias за compatibility со постоечкиот код
SnakeLadderGame = P2PSnakeLadderGame