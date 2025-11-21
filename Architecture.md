# SyncWave - Complete Architecture Analysis

## 1. HIGH-LEVEL ARCHITECTURE OVERVIEW

### System Purpose
SyncWave is a **hybrid Rust+Python multi-device audio broadcasting system** designed to stream system audio from one source to multiple devices simultaneously with low latency (sub-150ms). It enables synchronized audio playback across multiple receivers for use cases like watch parties, gaming sessions, and multi-room audio setups.

### Architectural Style
- **Hybrid Language Architecture**: Performance-critical audio capture in Rust, application logic and UI in Python
- **Client-Server Network Architecture**: UDP-based broadcasting with optional TCP for network streaming
- **Modular Design**: Separated concerns (UI, audio processing, network, sync)
- **Event-Driven**: Asynchronous audio streaming with callback-based processing

### Major Components

```
┌─────────────────────────────────────────────────────────────┐
│                    SyncWave Application                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐      │
│  │  Python GUI    │  │   Python     │  │   Rust      │      │
│  │  Layer         │──│   Bridge     │──│   Core      │      │
│  │ (CustomTkinter)│  │   (PyO3)     │  │  (cpal)     │      │
│  └────────────────┘  └──────────────┘  └─────────────┘      │
│         │                                      │            │
│         │                                      │            │
│  ┌──────▼──────────────────────────────────────▼───────┐    │
│  │         Audio Sync & Network Engine                 │    │
│  │  - Multi-device sync                                │    │
│  │  - UDP/TCP streaming                                │    │
│  │  - Jitter buffering                                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                  │
└──────────────────────────┼─────────────────────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
        ┌───────▼───────┐     ┌──────▼──────┐
        │  Local Audio  │     │   Network   │
        │   Devices     │     │   Clients   │
        └───────────────┘     └─────────────┘
```

### Key Interactions

1. **Audio Capture Flow**: Rust Core → Python Bridge → Network/Local Output
2. **UI Control Flow**: GUI → Configuration → Audio Engine → Devices
3. **Network Flow**: Server (Rust/Python) → UDP/TCP → Client (Python) → Audio Output
4. **Sync Flow**: Timestamp injection → Network transmission → Jitter buffer → Synchronized playback

---

## 2. MODULE-LEVEL ARCHITECTURE

### 2.1 Rust Audio Core (`src/lib.rs`)

**Purpose**: High-performance audio capture using WASAPI loopback with microsecond-precision timestamping.

**How It Works Internally**:
- Uses `cpal` library to access Windows WASAPI loopback interface
- Captures audio from default output device (what the system is playing)
- Creates UDP socket for network transmission
- Implements custom protocol with headers and timestamped packets
- Releases Python GIL during audio streaming for true parallelism

**Important Functions**:
```rust
start_audio_server(target_ip, target_port, use_compression, broadcast)
  ↓
  1. Create UDP socket (with broadcast flag if enabled)
  2. Get default audio device config (auto-detect sample rate/channels)
  3. Send header packets (5x for redundancy):
     [MAGIC(4)][VERSION(1)][SAMPLE_RATE(4)][CHANNELS(2)][COMPRESSION(1)]
  4. Build input stream with callback:
     - Convert f32 audio samples to bytes
     - Create packet: [TYPE(1)][TIMESTAMP(8)][SIZE(2)][DATA(n)]
     - Send via UDP
     - Resend header every 1000 packets
  5. Start stream and release GIL (py.allow_threads)
```

**Input**: Python function call with network parameters
**Output**: Continuous UDP audio packets to network

**Key Classes/Structs**: None (functional programming style)

**Data Flow**:
```
Windows Audio System → WASAPI Loopback → cpal → f32 samples 
  → Timestamping → UDP Socket → Network
```

---

### 2.2 Python-Rust Bridge (`PyO3`)

**Purpose**: Expose Rust functionality to Python with minimal overhead.

**How It Works**:
- `PyO3` generates Python-compatible module (`syncwave_core.pyd`)
- `#[pyfunction]` decorator exposes Rust functions to Python
- `#[pymodule]` creates importable Python module
- Type conversion handled automatically by PyO3
- GIL release allows concurrent Python execution

**Integration Points**:
```python
import syncwave_core
syncwave_core.start_audio_server(ip, port, compression, broadcast)
```

---

### 2.3 Main GUI Application (`syncwave_app.py`)

**Purpose**: Professional desktop application with modern UI for server/receiver control.

**How It Works Internally**:
- CustomTkinter provides dark-themed modern UI
- Tab-based interface (Server, Receiver, Settings, Stats)
- Threading model: Main thread for UI, daemon threads for audio processing
- Configuration persistence via JSON file (`~/.syncwave/config.json`)

**Important Classes**:

#### `SyncWaveApp(ctk.CTk)`
Main application window.

**Key Methods**:
- `create_ui()`: Builds tabbed interface
- `create_server_tab()`: Server configuration UI
  - Mode selection (Single/Broadcast/Multi-target)
  - IP/Port configuration
  - Multi-target device list management
- `create_receiver_tab()`: Receiver configuration UI
  - Port and jitter buffer settings
  - Audio level meters
  - Real-time statistics display
- `start_server()`: Launches Rust audio server in daemon thread
- `start_receiver()`: Launches Python receiver in daemon thread
- `save_config()` / `load_config()`: Settings persistence

**Data Flow**:
```
User Input → UI Event → Configuration Update → Thread Creation 
  → Rust Core or Python Receiver → Status Update → UI Feedback
```

---

### 2.4 Enhanced Receiver (`receiver_enhanced.py`)

**Purpose**: Production-quality audio receiver with jitter buffering, latency measurement, and optional Opus decompression.

**How It Works Internally**:
1. Binds UDP socket to listen port
2. Waits for header packet to auto-configure
3. Initializes PyAudio output stream
4. Implements jitter buffer for packet reordering
5. Continuously receives packets, measures latency, plays audio

**Important Classes**:

#### `JitterBuffer`
Lock-protected circular buffer for smooth playback.

**Methods**:
- `add(data)`: Thread-safe append
- `get()`: Returns packet only if buffer >= min threshold (prevents underrun)
- `size()`: Current buffer occupancy

**How It Works**:
```python
while True:
    packet = recv_udp()
    jitter_buffer.add(packet.data)
    
    # Only play if buffer has minimum packets
    if jitter_buffer.size() >= JITTER_BUFFER_MIN:
        audio_data = jitter_buffer.get()
        audio_stream.write(audio_data)  # Play to speakers
```

**Key Functions**:
- `parse_header(data)`: Extracts sample rate, channels, compression from 12-byte header
- `parse_audio_packet(data)`: Extracts timestamp and audio data
- `get_timestamp_us()`: Microsecond-precision timestamp for latency calculation

**Data Flow**:
```
UDP Socket → Header Parse (auto-config) → Opus Decode (if enabled) 
  → Jitter Buffer → PyAudio Stream → Speakers
```

**Latency Calculation**:
```python
latency_us = receive_time - packet.timestamp
latency_ms = latency_us / 1000
```

---

### 2.5 Silent Receiver (`receiver_silent.py`)

**Purpose**: Testing receiver that validates packets without audio playback (prevents feedback loops during single-machine testing).

**How It Works**:
- Same packet parsing as enhanced receiver
- No PyAudio initialization
- Only prints statistics (packet count, bitrate, latency)
- Useful for development and debugging

---

### 2.6 Build System (`build_app.py`, `syncwave.spec`)

**Purpose**: Create standalone Windows executable with all dependencies bundled.

**How It Works**:
1. `build_app.py` orchestrates the build process:
   - Checks Python dependencies
   - Builds Rust core via `maturin develop --release`
   - Invokes PyInstaller with spec file
2. `syncwave.spec` defines packaging:
   - Includes `syncwave_core.pyd` (Rust DLL)
   - Bundles CustomTkinter assets
   - Hides console window (`console=False`)
   - Enables UPX compression

**Output**: Single executable `dist/SyncWave.exe` (~20-40 MB)

---

### 2.7 Device Management (`check_devices.py`)

**Purpose**: Simple utility to enumerate available audio output devices.

**How It Works**:
- Calls Rust function (planned) or uses PyAudio
- Lists device index, name, and capabilities

---

## 3. RUNTIME DATA FLOW

### 3.1 Audio Capture → Broadcast Pipeline

```
┌────────────────────────────────────────────────────────────┐
│ 1. AUDIO SOURCE (Windows System Audio)                    │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 2. WASAPI LOOPBACK CAPTURE (Rust - src/lib.rs)            │
│    - Captures f32 audio samples (44.1kHz or 48kHz)        │
│    - 2 channels (stereo)                                   │
│    - Sample format: Float32                                │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 3. PACKET CREATION (Rust)                                 │
│    a. Convert f32 samples → u8 bytes                       │
│    b. Get microsecond timestamp                            │
│    c. Build packet:                                        │
│       [TYPE(1)][TIMESTAMP(8)][SIZE(2)][AUDIO_DATA(n)]    │
│    d. Every 1000 packets: resend header                   │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 4. NETWORK TRANSMISSION (UDP Socket)                      │
│    - Socket type: SOCK_DGRAM (UDP)                        │
│    - Broadcast flag set if broadcast mode                 │
│    - Target IP/Port from configuration                    │
│    - Packet size: ~2KB-8KB (varies with buffer size)      │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 5. NETWORK LAYER (LAN/WiFi)                               │
│    - UDP packets routed to receiver(s)                     │
│    - No guaranteed delivery (fire-and-forget)             │
│    - Latency: ~2-50ms on LAN, ~20-200ms on WiFi          │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 6. RECEIVER UDP SOCKET (Python - receiver_enhanced.py)    │
│    - Binds to 0.0.0.0:5555 (listens on all interfaces)   │
│    - Receives packets (blocking or timeout)               │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 7. PACKET PARSING (Python)                                │
│    a. Check packet type (header or audio)                 │
│    b. If header: auto-configure PyAudio                   │
│    c. If audio: extract timestamp and data                │
│    d. Calculate latency: now() - timestamp                │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 8. JITTER BUFFER (Python - JitterBuffer class)            │
│    - Add packet to circular buffer (thread-safe)          │
│    - Wait until buffer ≥ min threshold (e.g., 3 packets) │
│    - Pop oldest packet for playback                       │
│    - Purpose: Smooth out network jitter/reordering       │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────────────┐
│ 9. AUDIO PLAYBACK (PyAudio)                               │
│    - Stream format: paFloat32 or paInt16                  │
│    - Write audio data to stream buffer                    │
│    - Audio driver plays to speakers/headphones            │
└────────────────────────────────────────────────────────────┘
```

### 3.2 Threading Model

**Main Application (syncwave_app.py)**:
```
Main Thread (UI)
├── Daemon Thread: Rust Audio Server (GIL released)
│   └── Continuously captures and sends audio
├── Daemon Thread: Python Receiver (blocking UDP recv)
│   └── Receives packets and plays audio
└── Periodic UI Updates (after() callbacks)
    └── Update stats, meters, status labels
```

**Key Characteristics**:
- **UI Thread**: Handles all CustomTkinter events, never blocks
- **Audio Threads**: Daemon threads (exit when main thread exits)
- **GIL Release**: Rust audio server releases GIL via `py.allow_threads()`, enabling true parallelism
- **Thread Safety**: JitterBuffer uses locks, UDP sockets are thread-safe

---

## 4. NETWORKING ARCHITECTURE

### 4.1 Protocols Used

#### **Primary: UDP (User Datagram Protocol)**
- **Port**: 5555 (configurable)
- **Advantages**:
  - Low latency (no connection handshake)
  - No retransmission overhead
  - Suitable for real-time audio
- **Disadvantages**:
  - No guaranteed delivery
  - Packets can arrive out of order
  - No congestion control
- **Mitigation**: Jitter buffer handles reordering, redundant headers handle packet loss

#### **Secondary: TCP (Planned for network streaming)**
- Used in `network_server.py` / `network_client.py` (mentioned in docs but not fully implemented in provided code)
- Port 5555
- Reliable delivery for control messages and client management

---

### 4.2 Broadcast Logic

**Single Target Mode**:
```rust
socket.send_to(&packet, "192.168.1.100:5555")
```
- Sends to one specific IP:Port
- Most efficient for one-to-one streaming

**Broadcast Mode**:
```rust
socket.set_broadcast(true).unwrap();
socket.send_to(&packet, "255.255.255.255:5555")
```
- Sends to all devices on local subnet
- All receivers on port 5555 receive packets
- No device discovery needed

**Multi-Target Mode** (GUI implementation):
```python
for ip, port in self.target_devices:
    thread = Thread(target=run_server, args=(ip, port))
    thread.start()
```
- Creates separate Rust server thread for each target
- Each thread sends to specific IP:Port
- More CPU/network overhead but targeted delivery

---

### 4.3 Discovery Logic

**Current Implementation**: None (manual IP entry)

**Planned Implementation** (mentioned in ROADMAP.md):
- **mDNS/Zeroconf**: Service type `_syncwave._tcp.local.`
- Servers broadcast availability
- Clients discover servers automatically
- Library: `zeroconf` (already in requirements.txt)

---

### 4.4 Packet Structure

#### **Header Packet** (12 bytes):
```
┌──────────┬─────────┬───────────────┬──────────┬─────────────┐
│  MAGIC   │ VERSION │  SAMPLE_RATE  │ CHANNELS │ COMPRESSION │
│ (4 bytes)│ (1 byte)│   (4 bytes)   │ (2 bytes)│  (1 byte)   │
└──────────┴─────────┴───────────────┴──────────┴─────────────┘
```
- **MAGIC**: `b"SYNC"` (identifies protocol)
- **VERSION**: Protocol version (currently 1)
- **SAMPLE_RATE**: 44100 or 48000 (little-endian u32)
- **CHANNELS**: 2 for stereo (little-endian u16)
- **COMPRESSION**: 0 = Raw, 1 = Opus

**Purpose**: Auto-configures receiver without manual settings

#### **Audio Packet** (variable length):
```
┌──────────┬──────────────┬──────────┬─────────────────┐
│   TYPE   │  TIMESTAMP   │   SIZE   │   AUDIO_DATA    │
│ (1 byte) │  (8 bytes)   │ (2 bytes)│   (n bytes)     │
└──────────┴──────────────┴──────────┴─────────────────┘
```
- **TYPE**: 0 = Raw PCM, 1 = Opus compressed
- **TIMESTAMP**: Microseconds since epoch (u64, little-endian)
- **SIZE**: Audio data length in bytes (u16, little-endian)
- **AUDIO_DATA**: Raw f32 samples as bytes

**Total Overhead**: 11 bytes per packet

---

## 5. AUDIO ARCHITECTURE

### 5.1 Audio Capture

**Technology**: Windows WASAPI Loopback (via `cpal` Rust library)

**How WASAPI Loopback Works**:
- Virtual audio endpoint that captures system audio output
- Equivalent to "Stereo Mix" but programmatic
- Captures **exactly what the speakers play** (post-mixer audio)
- No audio device routing required

**Capture Process**:
```rust
let device = host.default_output_device().unwrap();
let config = device.default_output_config().unwrap();
let stream = device.build_input_stream(&config, callback, error_fn);
stream.play();
```

**Key Parameters**:
- **Sample Rate**: Auto-detected (typically 44.1kHz or 48kHz)
- **Channels**: Auto-detected (typically 2 for stereo)
- **Format**: f32 (32-bit floating point, range -1.0 to 1.0)
- **Buffer Size**: Determined by OS/driver (typically 480-2048 samples)

---

### 5.2 Audio Processing

**Current Implementation**: None (raw audio passthrough)

**Frame Format**:
- Interleaved stereo: `[L, R, L, R, L, R, ...]`
- Each sample: 4 bytes (f32)
- Frame rate: sample_rate / buffer_size (e.g., 48000 / 480 = 100 frames/sec)

**Planned Processing** (not yet implemented):
- Volume control (per-device gain multipliers)
- Compression (Opus codec for bandwidth reduction)
- Noise reduction (optional)

---

### 5.3 Audio Synchronization

**Challenge**: Multiple receivers must play audio in sync despite:
- Variable network latency
- Different processing delays
- Clock drift between devices

**Current Sync Strategy**:

1. **Timestamping**: Every packet includes transmission time
2. **Latency Measurement**: Receiver calculates `receive_time - timestamp`
3. **Jitter Buffer**: Absorbs network timing variations
4. **Manual Delay Adjustment**: User sets per-device delay in GUI (planned feature)

**Sync Accuracy**:
- Measured latency: ~100-150ms on LAN
- Jitter buffer adds ~20-100ms (configurable)
- Total end-to-end latency: ~120-250ms
- Inter-device sync: ±10-50ms (depends on network jitter)

**Limitations**:
- No clock synchronization (NTP integration planned)
- No adaptive delay compensation
- No packet loss concealment (future: interpolation)

---

### 5.4 Audio Output

**Technology**: PyAudio (Python wrapper for PortAudio)

**Output Configuration**:
```python
stream = pyaudio.open(
    format=pyaudio.paFloat32,
    channels=2,
    rate=sample_rate,  # From header
    output=True,
    frames_per_buffer=2048
)
```

**Playback Process**:
```python
while receiving:
    audio_data = jitter_buffer.get()
    if audio_data:
        stream.write(audio_data)  # Blocking write to audio driver
```

**Multiple Device Output** (not fully implemented):
- GUI allows selecting multiple output devices
- Each device requires separate PyAudio stream
- Potential approach (from docs): Open one stream per device, write same data to all

---

### 5.5 Buffering / Jitter / Drift Strategy

#### **Jitter Buffer Implementation**:

```python
class JitterBuffer:
    def __init__(self, size=10):
        self.buffer = collections.deque(maxlen=size)  # FIFO queue
        self.lock = threading.Lock()
    
    def add(self, data):
        with self.lock:
            self.buffer.append(data)
    
    def get(self):
        with self.lock:
            if len(self.buffer) >= JITTER_BUFFER_MIN:  # e.g., 3
                return self.buffer.popleft()
            return None  # Buffer underrun protection
```

**Purpose**:
- **Jitter Absorption**: Network packets arrive at irregular intervals; buffer smooths this out
- **Reordering**: UDP doesn't guarantee order; buffer allows some out-of-order packets
- **Underrun Prevention**: Waits for minimum packets before starting playback

**Configuration**:
- **Size**: 5-50 packets (adjustable via GUI slider)
- **Min Threshold**: Typically size / 3
- **Trade-off**: Larger buffer = smoother playback but higher latency

#### **Drift Handling** (not implemented):

**Problem**: Sender and receiver clocks run at slightly different rates
- **Sender Clock**: 48000.00 Hz
- **Receiver Clock**: 48000.02 Hz (20 ppm error)
- **Result**: After 1 minute, 72 samples difference (audible clicks)

**Solutions** (for future implementation):
1. **Adaptive Buffering**: Dynamically adjust buffer size
2. **Sample Rate Conversion**: Resample audio to match clocks
3. **Time Stretching**: Slightly speed up/slow down playback
4. **Packet Dropping/Duplication**: Skip or repeat packets to compensate

---

## 6. DEPENDENCY & LIBRARY OVERVIEW

### 6.1 Rust Dependencies (`Cargo.toml`)

| Library | Version | Purpose | Why This Library |
|---------|---------|---------|------------------|
| **pyo3** | 0.20.0 | Python bindings | Industry-standard Rust↔Python bridge, zero-cost abstractions |
| **cpal** | 0.15.2 | Cross-platform audio | Best Rust audio library, WASAPI support, maintained actively |
| **socket2** | 0.5.5 | Low-level sockets | Better control than std::net (broadcast, buffer sizes) |
| **anyhow** | 1.0 | Error handling | Ergonomic error propagation, reduces boilerplate |
| **audiopus** | 0.3.0-rc.0 | Opus codec (disabled) | High-quality audio compression, low latency |

**Why Rust**:
- Zero-overhead audio capture (no GIL)
- Memory safety (no buffer overflows)
- Native performance (compiled to machine code)
- Easy Python integration via PyO3

---

### 6.2 Python Dependencies (`requirements.txt`)

| Library | Purpose | Why This Library |
|---------|---------|------------------|
| **pyaudiowpatch** | Audio I/O | PyAudio fork with WASAPI Loopback support (Windows) |
| **customtkinter** | GUI framework | Modern, dark-themed Tkinter replacement, easier than Qt |
| **numpy** | Audio array ops | Fast array operations, used for audio processing |
| **scipy** | Signal processing | Cross-correlation for calibration (future feature) |
| **sounddevice** | Alternative audio | Backup for PyAudio, more modern API |
| **soundfile** | Audio file I/O | Read/write WAV, FLAC, etc. for recording feature |
| **pillow** | Image processing | Load images for GUI icons/assets |
| **pycaw** | Windows audio API | Control system volume (future feature) |
| **comtypes** | COM interfaces | Windows API access (with pycaw) |
| **psutil** | System utilities | Process enumeration, system info |
| **zeroconf** | Service discovery | mDNS/Bonjour for network discovery (future) |
| **opuslib** | Opus codec | Python Opus encoder/decoder (future) |

**Build Tools**:
- **maturin** 0.20.0: Builds Rust extension modules for Python
- **pyinstaller**: Creates standalone executables

---

## 7. STRENGTHS & WEAKNESSES

### 7.1 Architectural Strengths

✅ **Hybrid Language Design**:
- Rust handles performance-critical audio capture (no GIL, zero overhead)
- Python handles UI and application logic (rapid development)
- Best of both worlds: speed + ease of use

✅ **Modular Architecture**:
- Clear separation: UI / audio / network / sync
- Easy to extend (add new features without modifying core)
- Testable components (each module can be tested independently)

✅ **Cross-Platform Foundation**:
- `cpal` supports Windows, macOS, Linux
- `customtkinter` runs on all major platforms
- UDP networking is platform-agnostic

✅ **Flexible Deployment**:
- Source code for developers
- Standalone executable for end users
- No Python installation required for .exe

✅ **Low-Latency Design**:
- WASAPI Loopback (lowest latency capture on Windows)
- UDP for minimal network overhead
- Jitter buffer optimized for real-time streaming

✅ **Extensibility**:
- Plugin architecture possible (Python modules)
- Compression support ready (Opus integration)
- Network discovery ready (zeroconf imported)

---

### 7.2 Potential Bottlenecks

⚠️ **Network Bandwidth**:
- **Current**: ~3000 kbps per receiver (raw f32 audio at 48kHz stereo)
- **Impact**: WiFi saturation with 3+ receivers
- **Mitigation**: Enable Opus compression (reduces to ~128 kbps, 23x reduction)

⚠️ **UDP Reliability**:
- **Issue**: Packets can be lost or reordered
- **Impact**: Audio clicks/pops on poor networks
- **Mitigation**: Jitter buffer helps, but no forward error correction

⚠️ **Single-Threaded Audio Capture** (Rust):
- **Current**: One audio stream per server instance
- **Issue**: Multi-target mode creates multiple threads (CPU overhead)
- **Better Approach**: Single capture thread, multiple send threads

⚠️ **GIL Contention** (Python Receiver):
- **Issue**: UDP recv and PyAudio playback both hold GIL
- **Impact**: Latency spikes on CPU-bound systems
- **Mitigation**: Rust receiver (future) or multiprocessing

⚠️ **Memory Usage**:
- **Jitter Buffer**: ~10 packets * 8KB = 80KB per receiver (negligible)
- **PyInstaller Executable**: 20-40 MB (acceptable)
- **No Leak Detection**: Need memory profiling for long-running sessions

---

### 7.3 Missing Components / TODOs

❌ **Clock Synchronization**:
- No NTP or PTP implementation
- Drift accumulates over time (audible after ~1 hour)
- **Needed**: Adaptive buffering or sample rate conversion

❌ **Packet Loss Concealment**:
- No interpolation or error concealment
- Lost packets = silence or clicks
- **Needed**: FEC (forward error correction) or interpolation

❌ **Encryption**:
- Audio sent in plain text
- **Privacy Risk**: Anyone on network can eavesdrop
- **Needed**: TLS for TCP, DTLS for UDP, or AES encryption

❌ **Authentication**:
- No server authentication
- Anyone can connect to receiver
- **Needed**: Password or token-based auth

❌ **Auto-Calibration** (mentioned in docs, not in code):
- Feature documented but not implemented
- Would use cross-correlation to detect Bluetooth latency
- **File**: `calibration_engine.py` (referenced but not provided)

❌ **Network Streaming Client/Server** (mentioned in docs, not in code):
- `network_server.py` and `network_client.py` referenced but not in codebase
- TCP-based streaming with client management
- **Status**: Documented but not implemented

❌ **Opus Compression** (code ready, not enabled):
- `audiopus` dependency disabled in Cargo.toml
- Requires CMake to build
- **Status**: Ready to enable, needs build system fix

❌ **Multi-Device Local Sync** (partially implemented):
- GUI has multi-device support
- Sync engine not fully implemented
- **Needed**: Per-device PyAudio streams with delay compensation

❌ **Mobile App** (planned):
- Extensive documentation
- No implementation
- **Needed**: Separate mobile project (Flutter/React Native)

❌ **Recording Feature** (planned):
- Save audio streams to files
- Multi-track recording
- **Needed**: New module with `soundfile` integration

---

## 8. SEQUENCE DIAGRAMS (Text Form)

### 8.1 Host Flow (Audio Broadcasting)

```
User                GUI              Rust Core         Network         Receiver
 │                   │                    │               │               │
 │  Click "Start    │                    │               │               │
 │   Server"        │                    │               │               │
 ├──────────────────>│                    │               │               │
 │                   │  start_audio_      │               │               │
 │                   │   server(ip,port)  │               │               │
 │                   ├───────────────────>│               │               │
 │                   │                    │ Create UDP    │               │
 │                   │                    │  socket       │               │
 │                   │                    ├───────────────>│               │
 │                   │                    │               │               │
 │                   │                    │ Send Header   │               │
 │                   │                    │  (5x)         │               │
 │                   │                    ├───────────────┼──────────────>│
 │                   │                    │               │               │
 │                   │  [Thread Start]    │               │               │
 │                   │  [GIL Released]    │               │               │
 │                   │                    │               │               │
 │                   │                    │ WASAPI        │               │
 │                   │                    │  Loopback     │               │
 │                   │                    │  Capture      │               │
 │                   │                    │<──────────────┤               │
 │                   │                    │               │               │
 │                   │                    │ Timestamp     │               │
 │                   │                    │  & Packet     │               │
 │                   │                    │  Creation     │               │
 │                   │                    │───────┐       │               │
 │                   │                    │       │       │               │
 │                   │                    │<──────┘       │               │
 │                   │                    │               │               │
 │                   │                    │ Send Audio    │               │
 │                   │                    │  Packet       │               │
 │                   │                    ├───────────────┼──────────────>│
 │                   │                    │               │               │
 │                   │                    │ [Repeat]      │               │
 │                   │                    │               │               │
 │                   │  Update Status     │               │               │
 │                   │   "Server Running" │               │               │
 │  Visual Feedback  │<───────────────────┤               │               │
 │<──────────────────┤                    │               │               │
 │                   │                    │               │               │
 │  Click "Stop     │                    │               │               │
 │   Server"        │                    │               │               │
 ├──────────────────>│                    │               │               │
 │                   │  [Thread Exit]     │               │               │
 │                   │  (Daemon thread    │               │               │
 │                   │   terminates)      │               │               │
 │                   │                    │               │               │
```

---

### 8.2 Receiver Flow (Audio Playback)

```
User              GUI           UDP Socket      JitterBuffer    PyAudio       Speaker
 │                 │                 │               │             │             │
 │  Click "Start   │                 │               │             │             │
 │   Receiver"     │                 │               │             │             │
 ├────────────────>│                 │               │             │             │
 │                 │  Create Socket  │               │             │             │
 │                 │  bind(0.0.0.0:  │               │             │             │
 │                 │       5555)     │               │             │             │
 │                 ├────────────────>│               │             │             │
 │                 │                 │               │             │             │
 │                 │  [Thread Start] │               │             │             │
 │                 │                 │               │             │             │
 │                 │                 │ recv() [Wait] │             │             │
 │                 │                 │<──────────────┤             │             │
 │                 │                 │               │             │             │
 │                 │                 │ Header Packet │             │             │
 │                 │                 │  Received     │             │             │
 │                 │                 │───────────────>│             │             │
 │                 │                 │               │             │             │
 │                 │  Parse Header   │               │             │             │
 │                 │  (sample_rate,  │               │             │             │
 │                 │   channels)     │               │             │             │
 │                 │<────────────────┤               │             │             │
 │                 │                 │               │             │             │
 │                 │  Open PyAudio   │               │             │             │
 │                 │   Stream        │               │             │             │
 │                 ├────────────────────────────────────────────>│             │
 │                 │                 │               │             │             │
 │                 │                 │ [Main Loop]   │             │             │
 │                 │                 │               │             │             │
 │                 │                 │ Audio Packet  │             │             │
 │                 │                 │  Received     │             │             │
 │                 │                 │───────────────>│             │             │
 │                 │                 │               │             │             │
 │                 │                 │ Calculate     │             │             │
 │                 │                 │  Latency      │             │             │
 │                 │                 │───────┐       │             │             │
 │                 │                 │       │       │             │             │
 │                 │                 │<──────┘       │             │             │
 │                 │                 │               │             │             │
 │                 │                 │ Add to Buffer │             │             │
 │                 │                 ├──────────────>│             │             │
 │                 │                 │               │             │             │
 │                 │                 │               │ Get Packet  │             │
 │                 │                 │               │ (if >= min) │             │
 │                 │                 │               ├────────────>│             │
 │                 │                 │               │             │             │
 │                 │                 │               │             │ Play Audio  │
 │                 │                 │               │             ├────────────>│
 │                 │                 │               │             │             │
 │  Update Stats   │                 │               │             │             │
 │  (Latency, kbps)│                 │               │             │             │
 │<────────────────┤                 │               │             │             │
 │                 │                 │               │             │             │
 │                 │                 │ [Repeat]      │             │             │
 │                 │                 │               │             │             │
```

---

### 8.3 Sync Logic Flow (Timestamp-Based)

```
Server                                         Receiver
  │                                               │
  │ 1. Capture Audio Sample                      │
  │    (from WASAPI)                             │
  │───────────┐                                  │
  │           │                                  │
  │<──────────┘                                  │
  │                                              │
  │ 2. Get Current Timestamp                     │
  │    timestamp = now_us()                      │
  │    (e.g., 1700000000000000 μs)              │
  │───────────┐                                  │
  │           │                                  │
  │<──────────┘                                  │
  │                                              │
  │ 3. Create Packet                             │
  │    [TYPE][timestamp][SIZE][audio_data]       │
  │───────────┐                                  │
  │           │                                  │
  │<──────────┘                                  │
  │                                              │
  │ 4. Send via UDP                              │
  │─────────────────────────────────────────────>│
  │                                              │
  │            [Network Delay: ~5-50ms]          │
  │                                              │
  │                                              │ 5. Packet Arrives
  │                                              │    recv_time = now_us()
  │                                              │    (e.g., 1700000000050000 μs)
  │                                              │───────────┐
  │                                              │           │
  │                                              │<──────────┘
  │                                              │
  │                                              │ 6. Calculate Latency
  │                                              │    latency = recv_time - timestamp
  │                                              │    latency = 50000 μs = 50 ms
  │                                              │───────────┐
  │                                              │           │
  │                                              │<──────────┘
  │                                              │
  │                                              │ 7. Add to Jitter Buffer
  │                                              │    buffer.add(audio_data)
  │                                              │───────────┐
  │                                              │           │
  │                                              │<──────────┘
  │                                              │
  │                                              │ 8. Wait for Min Buffer
  │                                              │    if buffer.size() >= 3:
  │                                              │       packet = buffer.get()
  │                                              │───────────┐
  │                                              │           │
  │                                              │<──────────┘
  │                                              │
  │                                              │ 9. Play Audio
  │                                              │    pyaudio_stream.write(packet)
  │                                              │───────────┐
  │                                              │           │
  │                                              │<──────────┘
  │                                              │
  │                                              │ [Audio output to speakers]
  │                                              │
```

**Key Sync Insights**:
1. **Timestamp Authority**: Server's clock is the source of truth
2. **Latency Measurement**: Receiver knows how late each packet is
3. **Jitter Absorption**: Buffer smooths out timing variations
4. **No Clock Sync**: Assumes clocks roughly synchronized (limitation)

---

## 9. INFERRED INSIGHTS & ANALYSIS

### 9.1 Assumptions

**Network Assumptions**:
- All devices on same subnet (broadcast mode relies on this)
- Stable network (UDP loss rate < 1%)
- MTU supports large packets (8KB max)
- Firewall allows UDP port 5555

**Audio Assumptions**:
- Sample rate stable (no drift compensation)
- All receivers can handle sample rate (44.1 or 48 kHz)
- Audio devices support f32 or int16 format
- WASAPI available (Windows only currently)

**Timing Assumptions**:
- System clocks reasonably synchronized (±100ms)
- Latency variation < jitter buffer size
- No long-term drift correction needed

**User Assumptions**:
- Technical knowledge (understand IP addresses, ports)
- Local network control (can modify firewall)
- Patience for setup (no plug-and-play yet)

---

### 9.2 Potential Improvements

🔧 **Architecture**:
1. **Rust Receiver**: Rewrite receiver in Rust for lower latency and no GIL contention
2. **Shared Capture Thread**: Single audio capture, multiple network senders (efficient multi-target)
3. **Plugin System**: Dynamic module loading for extensibility
4. **Microservices**: Separate capture, encoding, networking into services

🔧 **Performance**:
1. **Zero-Copy Networking**: Use `sendmmsg` for batch UDP sends
2. **SIMD Audio Processing**: Vectorized operations for sample conversion
3. **Lock-Free Jitter Buffer**: Avoid mutex overhead with atomic ring buffer
4. **Thread Pinning**: CPU affinity for audio threads (reduce context switching)

🔧 **Networking**:
1. **FEC (Forward Error Correction)**: Reed-Solomon codes for packet loss recovery
2. **Adaptive Bitrate**: Reduce quality on poor networks
3. **WebRTC Integration**: Use established protocol stack
4. **QUIC Protocol**: UDP with reliability (better than TCP for real-time)

🔧 **Sync**:
1. **NTP Client**: Synchronize clocks across devices
2. **Adaptive Jitter Buffer**: Dynamically adjust based on network conditions
3. **Clock Drift Compensation**: Sample rate conversion or time stretching
4. **PTP (Precision Time Protocol)**: Microsecond-accurate clock sync

🔧 **User Experience**:
1. **Auto-Discovery UI**: Visual device picker (no IP entry)
2. **Wizard-Based Setup**: Step-by-step guided configuration
3. **Presets**: Save common configurations (e.g., "Movie Night", "Gaming")
4. **Mobile App**: Use phone as remote control or receiver

🔧 **Security**:
1. **AES Encryption**: Encrypt audio data
2. **Authentication Tokens**: Prevent unauthorized connections
3. **Certificate Pinning**: Verify server identity
4. **Rate Limiting**: Prevent DoS attacks

---

### 9.3 Incomplete Features (From Docs vs. Code)

**Documented but Missing**:
1. ❌ **Auto-Calibration** (`calibration_engine.py`): Referenced extensively in docs, not in codebase
2. ❌ **Network Streaming Client/Server**: `network_server.py` / `network_client.py` mentioned, not implemented
3. ❌ **Volume Control**: GUI has sliders, but no implementation in audio engine
4. ❌ **Multi-Device Sync Engine**: GUI supports adding multiple devices, no sync logic
5. ❌ **Opus Compression**: Code ready, but disabled in Cargo.toml (needs CMake)

**Partially Implemented**:
1. ⚠️ **Multi-Target Broadcasting**: GUI creates threads, but inefficient (one server per target)
2. ⚠️ **Configuration Persistence**: Saving works, but not all settings saved
3. ⚠️ **Audio Meters**: UI elements exist, but not connected to actual audio levels

---

### 9.4 Architectural Style Assessment

**Current Style**: **Modular Hybrid Monolith**

**Characteristics**:
- **Hybrid Language**: Rust core + Python application layer
- **Modular**: Clear separation of concerns (UI, audio, network)
- **Monolithic Deployment**: Single executable or source tree
- **Not Microservices**: Tightly coupled components (GUI calls Rust directly)

**Fits Best As**:
- **Desktop Application**: Designed for local installation
- **Peer-to-Peer**: Direct device-to-device streaming (no central server)
- **Real-Time System**: Low-latency audio focus

**Evolution Path**:
- **Current**: Monolithic hybrid (good for desktop app)
- **Future v1**: Plugin architecture (extensible modules)
- **Future v2**: Microservices (capture/encode/stream/play as separate services)
- **Future v3**: Cloud-hosted relay servers (for internet streaming)

---

### 9.5 Production Readiness Assessment

**Ready for Production** ✅:
- [x] Core audio capture works
- [x] UDP streaming functional
- [x] Jitter buffer implemented
- [x] GUI usable
- [x] Standalone executable builds

**Needs Work for Production** ⚠️:
- [ ] No error recovery (crash on network failure)
- [ ] No logging system (only print statements)
- [ ] No telemetry (can't diagnose user issues)
- [ ] No auto-updates (manual reinstall required)
- [ ] No crash reporting
- [ ] No unit tests
- [ ] No integration tests
- [ ] No performance profiling
- [ ] No security auditing

**Critical Missing Features for v1.0**:
1. **Error Handling**: Graceful degradation on failures
2. **Logging**: Structured logging to file
3. **Auto-Discovery**: Remove manual IP entry
4. **Opus Compression**: Essential for WiFi with multiple clients
5. **Clock Sync**: Prevent drift over time

**Estimated Maturity**: **Beta** (functional but needs polish)

---

## 10. CONCLUSION

SyncWave is a well-architected **hybrid Rust+Python audio broadcasting system** with a solid foundation for multi-device audio synchronization. The use of Rust for performance-critical audio capture combined with Python for rapid UI development demonstrates excellent architectural judgment.

**Key Strengths**:
- Low-latency WASAPI loopback capture
- Clean modular design
- Cross-platform foundation
- Extensible architecture

**Key Weaknesses**:
- Missing production features (error handling, logging)
- Incomplete sync features (drift compensation, FEC)
- Security concerns (no encryption/auth)
- Documentation-code mismatch (some features documented but not implemented)

**Recommended Next Steps**:
1. Enable Opus compression (bandwidth reduction)
2. Implement auto-discovery (UX improvement)
3. Add error handling and logging (production readiness)
4. Complete missing features (calibration, network streaming)
5. Add tests (reliability)

Overall, SyncWave is a **promising project with strong fundamentals** that needs additional development to reach production quality. The architecture is sound and can scale to support the planned features in the roadmap.

