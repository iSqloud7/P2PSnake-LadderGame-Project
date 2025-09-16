#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP Auth сервер за Snake & Ladder игра
ИСПРАВЕНА ВЕРЗИЈА ЗА WINDOWS
"""

import sys
import os
import io

# Исправи Unicode проблеми за Windows
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import hashlib
import datetime

app = FastAPI(title="Snake & Ladder Auth Server", version="1.0")

# CORS за локален развој
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# База на корисници во JSON
USERS_FILE = "game_users.json"


class UserCredentials(BaseModel):
    username: str
    password: str


def load_users():
    """Вчитај корисници"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading users: {e}")
    return {}


def save_users(users):
    """Зачувај корисници"""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving users: {e}")
        return False


def hash_password(password):
    """Хаширај лозинка"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def validate_credentials(username, password):
    """Валидирај креденцијали"""
    if len(username.strip()) < 3:
        return False, "Username must be at least 3 characters"

    if len(password.strip()) < 4:
        return False, "Password must be at least 4 characters"

    # Провери за invalid карактери
    invalid_chars = ['<', '>', '"', "'", '&']
    for char in invalid_chars:
        if char in username or char in password:
            return False, "Invalid characters in credentials"

    return True, "OK"


@app.get("/")
async def root():
    """Основна информација"""
    return {
        "message": "Snake & Ladder Auth Server",
        "version": "1.0",
        "endpoints": ["/register", "/login", "/status"],
        "users_count": len(load_users())
    }


@app.post("/register")
async def register(credentials: UserCredentials):
    """Регистрирај нов корисник"""
    try:
        # Валидација
        valid, msg = validate_credentials(credentials.username, credentials.password)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)

        users = load_users()

        # Провери дали корисникот постои
        if credentials.username.lower() in [u.lower() for u in users.keys()]:
            raise HTTPException(status_code=400, detail="Username already exists")

        # Создај нов корисник
        users[credentials.username] = {
            "password_hash": hash_password(credentials.password),
            "created_at": datetime.datetime.now().isoformat(),
            "last_login": None,
            "games_played": 0,
            "wins": 0,
            "losses": 0
        }

        if save_users(users):
            return {
                "success": True,
                "message": "User registered successfully",
                "username": credentials.username
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save user data")

    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/login")
async def login(credentials: UserCredentials):
    """Најави се"""
    try:
        users = load_users()

        # Најди го корисникот (case insensitive)
        user_key = None
        for key in users.keys():
            if key.lower() == credentials.username.lower():
                user_key = key
                break

        if not user_key:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        user_data = users[user_key]
        password_hash = hash_password(credentials.password)

        if user_data["password_hash"] != password_hash:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Ажурирај last_login
        user_data["last_login"] = datetime.datetime.now().isoformat()
        users[user_key] = user_data
        save_users(users)

        return {
            "success": True,
            "message": "Login successful",
            "username": user_key,
            "user_data": {
                "games_played": user_data.get("games_played", 0),
                "wins": user_data.get("wins", 0),
                "losses": user_data.get("losses", 0),
                "created_at": user_data.get("created_at")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/status")
async def status():
    """Статус на серверот"""
    users = load_users()
    return {
        "server_status": "active",
        "total_users": len(users),
        "users_file_exists": os.path.exists(USERS_FILE),
        "timestamp": datetime.datetime.now().isoformat()
    }


@app.get("/users")
async def list_users():
    """Листа на корисници (за debugging)"""
    users = load_users()
    return {
        "users": [
            {
                "username": username,
                "created_at": data.get("created_at"),
                "games_played": data.get("games_played", 0),
                "wins": data.get("wins", 0),
                "losses": data.get("losses", 0)
            }
            for username, data in users.items()
        ]
    }


if __name__ == "__main__":
    print("Starting Snake & Ladder Auth Server...")
    print("Server: http://localhost:8000")
    print("Status: http://localhost:8000/status")
    print("Users: http://localhost:8000/users")
    print("Press Ctrl+C to stop")
    print()

    # Создај празен users файл ако не постои
    if not os.path.exists(USERS_FILE):
        save_users({})
        print(f"Created {USERS_FILE}")

    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except KeyboardInterrupt:
        print("\nServer stopped")