"""
Enhanced Receiver with:
- Jitter buffer for smooth playback
- Latency measurement
- Better error handling
- Optional Opus decompression (if available)
"""
import socket
import pyaudio
import struct
import time
import collections
from threading import Thread, Lock

# Try to import opuslib, but continue without it if not available
try:
    import opuslib
    OPUS_AVAILABLE = True
except:
    OPUS_AVAILABLE = False
    print("⚠️  Opus library not available - will only support raw audio")

PORT = 5555
HEADER_MAGIC = b"SYNC"
PROTOCOL_VERSION = 1

# Packet types
PACKET_TYPE_RAW = 0
PACKET_TYPE_OPUS = 1

# Jitter buffer settings
JITTER_BUFFER_SIZE = 10  # Number of packets to buffer
JITTER_BUFFER_MIN = 3    # Minimum packets before starting playback

class JitterBuffer:
    """Simple jitter buffer to smooth out network variations"""
    def __init__(self, size=JITTER_BUFFER_SIZE):
        self.buffer = collections.deque(maxlen=size)
        self.lock = Lock()
        
    def add(self, data):
        with self.lock:
            self.buffer.append(data)
    
    def get(self):
        with self.lock:
            if len(self.buffer) >= JITTER_BUFFER_MIN:
                return self.buffer.popleft()
            return None
    
    def size(self):
        with self.lock:
            return len(self.buffer)

def parse_header(data):
    """Parse header packet: [MAGIC][VERSION][SAMPLE_RATE][CHANNELS][COMPRESSION]"""
    if len(data) < 12:
        return None
    
    magic = data[:4]
    if magic != HEADER_MAGIC:
        return None
    
    version = data[4]
    sample_rate = struct.unpack('<I', data[5:9])[0]
    channels = struct.unpack('<H', data[9:11])[0]
    compression = data[11]
    
    return {
        'version': version,
        'sample_rate': sample_rate,
        'channels': channels,
        'compression': compression,
        'compression_name': 'Opus' if compression == 1 else 'Raw'
    }

def parse_audio_packet(data):
    """Parse audio packet: [TYPE][TIMESTAMP][SIZE][DATA]"""
    if len(data) < 11:
        return None
    
    packet_type = data[0]
    timestamp = struct.unpack('<Q', data[1:9])[0]
    size = struct.unpack('<H', data[9:11])[0]
    audio_data = data[11:11+size]
    
    return {
        'type': packet_type,
        'timestamp': timestamp,
        'size': size,
        'data': audio_data
    }

def get_timestamp_us():
    """Get current timestamp in microseconds"""
    return int(time.time() * 1_000_000)

print(f"🎧 Enhanced receiver listening on port {PORT}...")
print("Features: Opus codec, Jitter buffer, Latency measurement\n")

# Setup UDP Socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))

# Wait for header packet
print("⏳ Waiting for configuration header...")
config = None
audio_packet_count = 0

while config is None:
    data, addr = sock.recvfrom(8192)
    config = parse_header(data)
    if config:
        print(f"✅ Config received from {addr}:")
        print(f"   Protocol Version: {config['version']}")
        print(f"   Sample Rate: {config['sample_rate']} Hz")
        print(f"   Channels: {config['channels']}")
        print(f"   Compression: {config['compression_name']}")
        if audio_packet_count > 0:
            print(f"   (Skipped {audio_packet_count} audio packets while waiting)")
        print()
    else:
        audio_packet_count += 1
        if audio_packet_count % 100 == 0:
            print(f"   Still waiting... ({audio_packet_count} packets received)")

# Setup Opus Decoder (if needed and available)
decoder = None
if config['compression'] == 1:
    if OPUS_AVAILABLE:
        try:
            decoder = opuslib.Decoder(config['sample_rate'], config['channels'])
            print("🎵 Opus decoder initialized")
        except Exception as e:
            print(f"⚠️  Opus decoder initialization failed: {e}")
            print("   Falling back to raw audio mode")
    else:
        print("⚠️  Compression enabled but Opus library not available")
        print("   Install Opus library to enable compression support")

# Initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paFloat32,
    channels=config['channels'],
    rate=config['sample_rate'],
    output=True,
    frames_per_buffer=2048
)

# Initialize jitter buffer
jitter_buffer = JitterBuffer(JITTER_BUFFER_SIZE)

print(f"🔊 Playing audio with jitter buffer ({JITTER_BUFFER_SIZE} packets)...\n")

# Statistics
packet_count = 0
bytes_received = 0
total_latency_us = 0
latency_count = 0
start_time = time.time()
last_report = start_time

try:
    while True:
        data, addr = sock.recvfrom(65536)
        
        # Skip header packets
        if len(data) == 12 and data[:4] == HEADER_MAGIC:
            continue
        
        # Parse audio packet
        packet = parse_audio_packet(data)
        if not packet:
            continue
        
        packet_count += 1
        bytes_received += len(data)
        
        # Calculate latency
        receive_time = get_timestamp_us()
        latency_us = receive_time - packet['timestamp']
        total_latency_us += latency_us
        latency_count += 1
        
        # Decode if needed
        if packet['type'] == PACKET_TYPE_OPUS and decoder:
            try:
                # Decode Opus to PCM
                # decode_float returns bytes (raw float data)
                pcm_data = decoder.decode_float(packet['data'], 2880, decode_fec=False)
                jitter_buffer.add(pcm_data)
            except Exception as e:
                print(f"⚠️  Opus decode error: {e}")
                continue
        else:
            # Raw audio data
            jitter_buffer.add(packet['data'])
        
        # Play from jitter buffer
        audio_data = jitter_buffer.get()
        if audio_data:
            stream.write(audio_data)
        
        # Report stats every 2 seconds
        now = time.time()
        if now - last_report >= 2.0:
            elapsed = now - start_time
            kbps = (bytes_received * 8) / (elapsed * 1000)
            avg_latency_ms = (total_latency_us / latency_count) / 1000 if latency_count > 0 else 0
            buffer_fill = jitter_buffer.size()
            
            compression_ratio = 0
            if config['compression'] == 1:
                uncompressed_bps = config['sample_rate'] * config['channels'] * 32  # bits
                compression_ratio = (kbps * 1000) / uncompressed_bps * 100
            
            print(f"📦 Packets: {packet_count:6d} | "
                  f"Rate: {kbps:7.1f} kbps | "
                  f"Latency: {avg_latency_ms:5.1f}ms | "
                  f"Buffer: {buffer_fill}/{JITTER_BUFFER_SIZE}", end="")
            
            if compression_ratio > 0:
                print(f" | Compression: {compression_ratio:.1f}%")
            else:
                print()
            
            last_report = now

except KeyboardInterrupt:
    print(f"\n\n⏹️  Stopped")
    elapsed = time.time() - start_time
    avg_latency_ms = (total_latency_us / latency_count) / 1000 if latency_count > 0 else 0
    
    print(f"\n📈 Final Stats:")
    print(f"   Packets received: {packet_count}")
    print(f"   Total data: {bytes_received/1024/1024:.2f} MB")
    print(f"   Average bitrate: {(bytes_received * 8) / (elapsed * 1000):.1f} kbps")
    print(f"   Average latency: {avg_latency_ms:.2f} ms")
    print(f"   Duration: {elapsed:.1f}s")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    sock.close()
