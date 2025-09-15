#!/usr/bin/env python3
"""
Главен starter script за WebRTC P2P Snake & Ladder игра
Автоматски ги проверува зависностите и стартува соодветните компоненти
"""

import sys
import subprocess
import importlib
import threading
import time
import os
from pathlib import Path


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
        'PIL': 'Pillow==10.1.0'
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
        'webrtc_snake_ladder_game.py'
    ]

    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
        else:
            print(f"✅ {file}")

    if missing_files:
        print(f"\n❌ Недостасуваат файлови: {', '.join(missing_files)}")
        return False

    return True


def start_signaling_server():
    """Стартај signaling сервер во background"""
    try:
        import subprocess
        process = subprocess.Popen([
            sys.executable, 'webrtc_signaling_server.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Чекај малку да се стартува
        time.sleep(2)

        # Провери дали сè уред
        if process.poll() is None:  # Сè уред работи
            print("✅ Signaling сервер стартуван (PID: {})".format(process.pid))
            return process
        else:
            print("❌ Грешка при стартување на signaling сервер")
            return None

    except Exception as e:
        print(f"❌ Неможе да се стартува signaling сервер: {e}")
        return None


def start_game_client():
    """Стартај игра клиент"""
    try:
        import webrtc_game_client
        client = webrtc_game_client.WebRTCGameClient()
        print("🎮 Игра клиент стартуван!")
        client.run()
        return True
    except Exception as e:
        print(f"❌ Грешка при стартување на игра клиент: {e}")
        return False


def show_menu():
    """Прикажи главно мени за избор на начин на стартување"""
    print("\n" + "=" * 50)
    print("🐍 WebRTC P2P Snake & Ladder игра")
    print("=" * 50)
    print()
    print("Изберете опција:")
    print("1. Стартај игра со автоматски signaling сервер")
    print("2. Стартај само игра клиент (signaling сервер веќе работи)")
    print("3. Стартај само signaling сервер")
    print("4. Покрени unit тестови")
    print("5. Излез")
    print()

    while True:
        try:
            choice = input("Внесете избор (1-5): ").strip()

            if choice == "1":
                print("\n🚀 Стартувам комплетна игра...")
                signaling_process = start_signaling_server()
                if signaling_process:
                    try:
                        start_game_client()
                    finally:
                        print("\n🛑 Затворам signaling сервер...")
                        signaling_process.terminate()
                        signaling_process.wait()
                break

            elif choice == "2":
                print("\n🎮 Стартувам игра клиент...")
                start_game_client()
                break

            elif choice == "3":
                print("\n📡 Стартувам signaling сервер...")
                print("Притиснете Ctrl+C за да застанете")
                try:
                    import webrtc_signaling_server
                    import asyncio
                    asyncio.run(webrtc_signaling_server.start_signaling_server())
                except KeyboardInterrupt:
                    print("\n🛑 Signaling сервер застанат")
                break

            elif choice == "4":
                print("\n🧪 Покренувам unit тестови...")
                try:
                    import test_webrtc_snake_ladder
                    test_webrtc_snake_ladder.run_tests()
                except ImportError:
                    print("❌ test_webrtc_snake_ladder.py не е најден")
                except Exception as e:
                    print(f"❌ Грешка при тестовите: {e}")
                break

            elif choice == "5":
                print("👋 Довидување!")
                break

            else:
                print("❌ Невалиден избор. Внесете 1-5.")

        except KeyboardInterrupt:
            print("\n\n👋 Довидување!")
            break
        except Exception as e:
            print(f"❌ Грешка: {e}")


def main():
    """Главна функција"""
    print("🔍 Проверувам системски барања...")

    # Провери Python верзија
    if not check_python_version():
        return

    # Провери файлови
    print("\n📁 Проверувам потребни файлови...")
    if not check_required_files():
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