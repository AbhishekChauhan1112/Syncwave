# SyncWave - Multi-Device Audio Broadcasting

**Broadcast audio to multiple devices simultaneously with perfect synchronization**

SyncWave is a powerful Python-based desktop application that enables you to play audio from one source (YouTube, Spotify, system audio) to multiple output devices at once - perfect for group movie watching, gaming sessions, or multi-room audio setups.

## ✨ Features

- 🎧 **Multi-Device Broadcasting**: Play one audio source to unlimited output devices simultaneously
- ⚡ **Zero Latency**: Advanced buffering ensures crystal-clear, synchronized playback
- 🎛️ **Individual Controls**: Volume and delay adjustment per device
- 🔊 **WASAPI Loopback**: Capture system audio (Stereo Mix) for seamless broadcasting
- 🎨 **Modern UI**: Dark-themed interface built with CustomTkinter
- 🖥️ **Windows Support**: Optimized for Windows 10/11

## 🎯 Use Cases

- **Movie Nights**: Everyone watches together with their own headphones
- **Gaming Sessions**: Multiple players hear in-game audio on individual headsets
- **Multi-Room Audio**: Broadcast music to speakers in different rooms
- **Silent Parties**: DJ streams to multiple Bluetooth headphones

## 🚀 Quick Start

### Installation

```powershell
# Clone the repository
git clone https://github.com/AbhishekChauhan1112/Syncwave.git
cd Syncwave

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Usage

```powershell
python SyncWave.py
```

1. Go to **Multi-Sync Broadcast** tab
2. Select **"Stereo Mix"** as Input Source
3. Click **"Add Output Device"** for each headphone/speaker
4. Play audio (YouTube, Spotify, etc.)
5. Click **"Start Sync"**

## 🛠️ Technologies

- **PyAudioWPatch**: WASAPI loopback capture for system audio
- **CustomTkinter**: Modern dark-themed GUI
- **NumPy**: Audio buffer management
- **PyCaw**: Windows audio device enumeration

## 📋 Requirements

- Windows 10/11
- Python 3.8+
- Multiple Bluetooth headphones or audio output devices

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## 📄 License

MIT License - see LICENSE file for details

## 👤 Author

**Abhishek Chauhan**  
GitHub: [@hi-manss](https://github.com/hi-manss/)

## 🤝 Contributer

**Himanshh Chauhan**
GitHub: [@AbhishekChauhan1112](https://github.com/AbhishekChauhan1112)



---

**Note**: For capturing system audio, ensure "Stereo Mix" is enabled in Windows Sound Settings.
