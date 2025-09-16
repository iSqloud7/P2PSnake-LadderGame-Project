#!/usr/bin/env python3
"""
Главен starter script за WebRTC P2P Snake & Ladder игра
ИСПРАВЕНА ВЕРЗИЈА ЗА WINDOWS
"""

import sys
import subprocess
import importlib
import threading
import time
import os
from pathlib import Path
import platform


def check_python_version():
    """Провери дали Python верзијата е соодветна"""
    if sys.version_info < (3, 8):
        print("❌ Грешка: Потребна е Python 3.8 или повисоко")
        print(f"   Вашата верзија: {sys.version}")
        return False
    return True


def check_and_install_dependencies():
    """Провери и инсталирај ги потребните библиотеки"""
    required_packages = {
        'aiortc': 'aiortc==1.6.0',
        'websockets': 'websockets==12.0',
        'PIL': 'Pillow==10.1.0',
        'fastapi': 'fastapi==0.104.1',
        'uvicorn': 'uvicorn==0.24.0',
        'requests': 'requests==2.31.0'
    }

    missing_packages = []

    for package, pip_name in required_packages.items():
        try:
            importlib.import_module(package)
            print(f"✅ {package} - инсталиран")
        except ImportError:
            print(f"❌ {package} - не е инсталиран")
            missing_packages.append(pip_name)

    if missing_packages:
        print("\n📦 Инсталирам потребни пакети...")
        try:
            subprocess.check_call([
                                      sys.executable, "-m", "pip", "install"
                                  ] + missing_packages)
            print("✅ Сите пакети се инсталирани успешно!")
            return True
        except subprocess.CalledProcessError:
            print("❌ Грешка при инсталирање. Обидете се рачно:")
            print(f"   pip install {' '.join(missing_packages)}")
            return False

    return True


def check_required_files():
    """Провери дали сите потребни файлови постојат"""
    required_files = [
        'webrtc_signaling_server.py',
        'webrtc_client.py',
        'webrtc_game_client.py',
        'webrtc_snake_ladder_game.py',
        'auth_server.py'
    ]

    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            missing_files.append(file)
            print(f"❌ {file} - не постои")

    if missing_files:
        print(f"\n❌ Недостасуваат файлови: {', '.join(missing_files)}")
        return False

    return True


def start_auth_server():
    """Стартај Auth HTTP сервер во background - Windows compatible"""
    try:
        print("🔄 Стартувам Auth сервер...")

        # Провери дали файлот постои
        if not os.path.exists('auth_server.py'):
            print("❌ auth_server.py не постои!")
            return None

        # За Windows, користи креирање на нов прозорец
        if platform.system() == "Windows":
            # CREATE_NEW_CONSOLE за да се отвори во посебен прозорец
            process = subprocess.Popen([
                sys.executable, 'auth_server.py'
            ],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        else:
            # За Linux/Mac
            process = subprocess.Popen([
                sys.executable, 'auth_server.py'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Чекај подолго за Windows
        time.sleep(5)

        # Провери дали процесот работи
        if process.poll() is None:
            print("✅ Auth сервер стартуван (PID: {})".format(process.pid))

            # Дополнителна проверка - тестирај HTTP поврзување
            try:
                import requests
                time.sleep(2)  # Дај малку повеќе време
                response = requests.get("http://localhost:8000/status", timeout=10)
                if response.status_code == 200:
                    print("✅ Auth сервер одговара на HTTP барања")
                    return process
                else:
                    print("⚠️ Auth сервер работи но не одговара правилно")
                    return process
            except Exception as e:
                print(f"⚠️ Auth сервер стартуван но нема HTTP одговор: {e}")
                return process
        else:
            # Прикажи ја грешката
            stdout, stderr = process.communicate()
            print("❌ Auth сервер се урна:")
            if stderr:
                print("STDERR:", stderr.decode())
            if stdout:
                print("STDOUT:", stdout.decode())
            return None

    except Exception as e:
        print(f"❌ Неможе да се стартува auth сервер: {e}")
        return None


def start_signaling_server():
    """Стартај signaling сервер во background - Windows compatible"""
    try:
        print("🔄 Стартувам Signaling сервер...")

        if not os.path.exists('webrtc_signaling_server.py'):
            print("❌ webrtc_signaling_server.py не постои!")
            return None

        # За Windows, користи креирање на нов прозорец
        if platform.system() == "Windows":
            process = subprocess.Popen([
                sys.executable, 'webrtc_signaling_server.py'
            ],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        else:
            process = subprocess.Popen([
                sys.executable, 'webrtc_signaling_server.py'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        time.sleep(3)

        if process.poll() is None:
            print("✅ Signaling сервер стартуван (PID: {})".format(process.pid))
            return process
        else:
            stdout, stderr = process.communicate()
            print("❌ Signaling сервер се урна:")
            if stderr:
                print("STDERR:", stderr.decode())
            if stdout:
                print("STDOUT:", stdout.decode())
            return None

    except Exception as e:
        print(f"❌ Неможе да се стартува signaling сервер: {e}")
        return None


def start_game_client():
    """Стартај игра клиент"""
    try:
        print("🎮 Стартувам игра клиент...")
        import webrtc_game_client
        client = webrtc_game_client.WebRTCGameClient()
        client.run()
        return True
    except Exception as e:
        print(f"❌ Грешка при стартување на игра клиент: {e}")
        return False


def start_servers_in_terminals():
    """Алтернативен начин - отвори сервери во посебни терминали"""
    print("\n🖥️ Отварам сервери во посебни прозорци...")

    if platform.system() == "Windows":
        # Windows команди
        try:
            # Auth сервер
            subprocess.Popen([
                'start', 'cmd', '/k',
                f'cd /d "{os.getcwd()}" && python auth_server.py'
            ], shell=True)
            print("✅ Auth сервер прозорец отворен")

            time.sleep(2)

            # Signaling сервер
            subprocess.Popen([
                'start', 'cmd', '/k',
                f'cd /d "{os.getcwd()}" && python webrtc_signaling_server.py'
            ], shell=True)
            print("✅ Signaling сервер прозорец отворен")

            return True

        except Exception as e:
            print(f"❌ Грешка при отварање терминали: {e}")
            return False
    else:
        # Linux/Mac команди
        try:
            subprocess.Popen(['gnome-terminal', '--', 'python3', 'auth_server.py'])
            time.sleep(1)
            subprocess.Popen(['gnome-terminal', '--', 'python3', 'webrtc_signaling_server.py'])
            return True
        except:
            try:
                subprocess.Popen(['xterm', '-e', 'python3', 'auth_server.py'])
                time.sleep(1)
                subprocess.Popen(['xterm', '-e', 'python3', 'webrtc_signaling_server.py'])
                return True
            except Exception as e:
                print(f"❌ Грешка при отварање терминали: {e}")
                return False


def show_menu():
    """Прикажи главно мени за избор на начин на стартување"""
    print("\n" + "=" * 60)
    print("🐍 WebRTC P2P Snake & Ladder игра со Auth систем")
    print("=" * 60)
    print()
    print("Изберете опција:")
    print("1. 🚀 Стартај комплетна игра (Auth + Signaling + Client)")
    print("2. 🖥️ Отвори сервери во посебни прозорци + Client")
    print("3. 🎮 Стартај само игра клиент (серверите веќе работат)")
    print("4. 🔐 Стартај само Auth сервер")
    print("5. 📡 Стартај само Signaling сервер")
    print("6. 🧪 Покрени unit тестови")
    print("7. 🔍 Провери server статус")
    print("8. ❌ Излез")
    print()

    while True:
        try:
            choice = input("Внесете избор (1-8): ").strip()

            if choice == "1":
                print("\n🚀 Стартувам комплетна игра (background процеси)...")

                # Стартај Auth сервер
                auth_process = start_auth_server()
                if not auth_process:
                    print("❌ Не можам да стартувам Auth сервер")
                    print("💡 Пробајте опција 2 или стартувајте рачно")
                    continue

                # Стартај Signaling сервер
                signaling_process = start_signaling_server()
                if not signaling_process:
                    print("❌ Не можам да стартувам Signaling сервер")
                    if auth_process:
                        auth_process.terminate()
                    print("💡 Пробајте опција 2 или стартувајте рачно")
                    continue

                try:
                    print("\n🎮 Чекам серверите да се стабилизираат...")
                    time.sleep(5)
                    start_game_client()
                finally:
                    print("\n🛑 Затворам сервери...")
                    if auth_process:
                        auth_process.terminate()
                        try:
                            auth_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            auth_process.kill()
                    if signaling_process:
                        signaling_process.terminate()
                        try:
                            signaling_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            signaling_process.kill()
                break

            elif choice == "2":
                if start_servers_in_terminals():
                    print("\n⏳ Чекам серверите да се стартуваат...")
                    time.sleep(8)
                    print("🎮 Стартувам игра клиент...")
                    start_game_client()
                else:
                    print("❌ Не можам да отворам терминали")
                break

            elif choice == "3":
                print("\n🎮 Стартувам игра клиент...")
                start_game_client()
                break

            elif choice == "4":
                print("\n🔐 Стартувам Auth сервер...")
                print("Притиснете Ctrl+C за да застанете")
                try:
                    import auth_server
                    import uvicorn
                    uvicorn.run(auth_server.app, host="127.0.0.1", port=8000)
                except KeyboardInterrupt:
                    print("\n🛑 Auth сервер застанат")
                except ImportError:
                    print("❌ auth_server.py или fastapi не се најдени")
                break

            elif choice == "5":
                print("\n📡 Стартувам Signaling сервер...")
                print("Притиснете Ctrl+C за да застанете")
                try:
                    import webrtc_signaling_server
                    import asyncio
                    asyncio.run(webrtc_signaling_server.start_signaling_server())
                except KeyboardInterrupt:
                    print("\n🛑 Signaling сервер застанат")
                break

            elif choice == "6":
                print("\n🧪 Покренувам unit тестови...")
                try:
                    import test_webrtc_snake_ladder
                    test_webrtc_snake_ladder.run_tests()
                except ImportError:
                    print("❌ test_webrtc_snake_ladder.py не е најден")
                except Exception as e:
                    print(f"❌ Грешка при тестовите: {e}")
                break

            elif choice == "7":
                print("\n🔍 Проверувам server статус...")
                check_server_status()
                input("\nПритиснете Enter за да продолжите...")

            elif choice == "8":
                print("👋 Довидување!")
                break

            else:
                print("❌ Невалиден избор. Внесете 1-8.")

        except KeyboardInterrupt:
            print("\n\n👋 Довидување!")
            break
        except Exception as e:
            print(f"❌ Грешка: {e}")


def check_server_status():
    """Провери го статусот на серверите"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    import websockets
    import asyncio

    print("Проверувам серверски статус...")

    # Провери Auth сервер
    try:
        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.3)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)

        response = session.get("http://localhost:8000/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Auth сервер: Активен ({data.get('total_users', 0)} корисници)")
        else:
            print("❌ Auth сервер: Одговара но има проблем")
    except Exception as e:
        print(f"❌ Auth сервер: Недостапен ({e})")

    # Провери Signaling сервер
    async def check_signaling():
        try:
            uri = "ws://localhost:8765"
            async with websockets.connect(uri, open_timeout=5) as websocket:
                await websocket.send('{"type": "ping"}')
                return True
        except Exception as e:
            return False

    try:
        signaling_ok = asyncio.run(check_signaling())
        if signaling_ok:
            print("✅ Signaling сервер: Активен")
        else:
            print("❌ Signaling сервер: Проблем со поврзување")
    except Exception as e:
        print(f"❌ Signaling сервер: Недостапен ({e})")


def main():
    """Главна функција"""
    print("🔍 Проверувам системски барања...")
    print(f"OS: {platform.system()} {platform.release()}")

    # Провери Python верзија
    if not check_python_version():
        return

    # Провери файлови
    print("\n📁 Проверувам потребни файлови...")
    if not check_required_files():
        print("\n💡 Креирајте ги недостасувачките файлови пред да продолжите.")
        return

    # Провери и инсталирај зависности
    print("\n📦 Проверувам Python библиотеки...")
    if not check_and_install_dependencies():
        return

    print("\n✅ Сите барања се исполнети!")

    # Прикажи мени
    show_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Програмот е прекинат од корисникот")
    except Exception as e:
        print(f"\n❌ Неочекувана грешка: {e}")
        print("💡 Проверете дали сите файлови се правилно инсталирани")