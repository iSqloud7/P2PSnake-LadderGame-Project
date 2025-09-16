WebRTC (Web Real Time Connection) P2P (Peer-To-Peer) Snake & Ladder Game

1.  Overview
This is a P2P version of the Snake & Ladder game that
uses WebRTC for direct communication between players without the need for a centralized server.
Once the connection is established, players communicate directly.

2.  System Requirements
- Python 3.8 or higher
- Operating System: Windows, macOS, Linux
- Internet connection (for connection establishment only)
- Minimum 4GB RAM
- 100MB free space

3.  Place all the following files in the same folder:
- signaling_server.py
- webrtc_client.py
- webrtc_game_client.py
- webrtc_snake_ladder_game.py
- requirements.txt

4.  Install required libraries
Core libraries:
- pip install aiortc==1.6.0
- pip install websockets==12.0
- pip install Pillow==10.1.0

# Or install from requirements.txt
- pip install -r requirements.txt
- pip install fastapi uvicorn requests aiortc websockets pillow

HOST:
webrtc_client.py ("ws://127.0.0.1:8765")
python http_websocket_server.py
ngrok http 8765
python start_game.py
option: 2

CLIENT:
webrtc_client.py ("ws://cfb21a011d26.ngrok-free.app/:8765")
python start_game.py
option: 2