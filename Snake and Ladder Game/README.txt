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