"""
Silent Receiver - For local testing without audio playback
This version receives and validates packets but doesn't play audio,
preventing feedback loops during single-machine testing.
"""
import socket
import struct
import time

PORT = 5555
HEADER_MAGIC = b"SYNC"

def parse_header(data):
    """Parse header packet: [MAGIC][SAMPLE_RATE][CHANNELS]"""
    if len(data) < 10:
        return None
    
    magic = data[:4]
    if magic != HEADER_MAGIC:
        return None
    
    sample_rate = struct.unpack('<I', data[4:8])[0]
    channels = struct.unpack('<H', data[8:10])[0]
    
    return {
        'sample_rate': sample_rate,
        'channels': channels
    }

print(f"🔇 Silent receiver listening on port {PORT}...")
print("(Audio packets are received but NOT played - prevents feedback loop)\n")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))

# Wait for header
print("⏳ Waiting for configuration header...")
print("   TIP: Start the server AFTER starting this receiver\n")
config = None
audio_packet_count = 0

while config is None:
    data, addr = sock.recvfrom(8192)
    config = parse_header(data)
    if config:
        print(f"✅ Config received from {addr}:")
        print(f"   Sample Rate: {config['sample_rate']} Hz")
        print(f"   Channels: {config['channels']}")
        if audio_packet_count > 0:
            print(f"   (Skipped {audio_packet_count} audio packets while waiting for header)")
        print(f"\n📊 Monitoring packets...\n")
    else:
        # Received audio data before header
        audio_packet_count += 1
        if audio_packet_count == 1:
            print(f"⚠️  Receiving audio packets (size: {len(data)} bytes)")
            print(f"   Waiting for header packet (10 bytes with 'SYNC' magic)...")
        elif audio_packet_count % 100 == 0:
            print(f"   Still waiting... ({audio_packet_count} audio packets received)")

# Statistics
packet_count = 0
bytes_received = 0
start_time = time.time()
last_report = start_time

try:
    while True:
        data, addr = sock.recvfrom(8192)
        
        # Skip header packets
        if len(data) == 10 and data[:4] == HEADER_MAGIC:
            continue
        
        packet_count += 1
        bytes_received += len(data)
        
        # Report every 2 seconds
        now = time.time()
        if now - last_report >= 2.0:
            elapsed = now - start_time
            kbps = (bytes_received * 8) / (elapsed * 1000)
            samples = bytes_received // 4  # f32 = 4 bytes
            duration_sec = samples / config['sample_rate'] / config['channels']
            
            print(f"📦 Packets: {packet_count:6d} | "
                  f"Data: {bytes_received/1024/1024:6.2f} MB | "
                  f"Rate: {kbps:7.1f} kbps | "
                  f"Audio: {duration_sec:.1f}s")
            last_report = now

except KeyboardInterrupt:
    print(f"\n⏹️  Stopped")
    elapsed = time.time() - start_time
    print(f"\n📈 Final Stats:")
    print(f"   Packets received: {packet_count}")
    print(f"   Total data: {bytes_received/1024/1024:.2f} MB")
    print(f"   Average bitrate: {(bytes_received * 8) / (elapsed * 1000):.1f} kbps")
    print(f"   Duration: {elapsed:.1f}s")
finally:
    sock.close()
