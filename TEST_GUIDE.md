# 🧪 SyncWave Testing Guide

## Quick Test Scenarios

---

## 🎯 Test 1: Single Device (Local Testing)

### Setup:
- **1 PC** with speakers/headphones
- Test on same machine

### Steps:

#### Option A: Using GUI (Easiest)

```powershell
# Terminal 1: Launch GUI
python syncwave_app.py
```

**In the GUI:**
1. **Server Tab:**
   - IP: `127.0.0.1` (localhost)
   - Port: `5555`
   - ✅ **UNCHECK** "Broadcast Mode"
   - Click **"Start Server"**
   - Should show: "🎵 Server Running"

2. **Receiver Tab:**
   - Port: `5555`
   - Jitter Buffer: `10`
   - Click **"Start Receiver"**
   - Should show: Audio meters moving, latency ~100-150ms

**Expected Result:**
- ✅ Audio plays from your speakers
- ✅ Latency display shows ~100-150ms
- ✅ Audio level meters visualize sound
- ✅ Stats tab shows packets/bitrate

---

#### Option B: Using Command Line

```powershell
# Terminal 1: Start Server
python start_server.py

# Terminal 2: Start Silent Receiver (no audio output)
python receiver_silent.py
```

**Expected Output:**
```
Server:
 Device config: 48000 Hz, 2 channels
 Sent header: 48000Hz, 2 channels, compression: Raw
 Server running with timestamps & latency measurement

Receiver:
📦 Received SYNC header
   Sample Rate: 48000 Hz
   Channels: 2
   Latency: 114ms
   Bitrate: 3079 kbps
```

---

## 🌐 Test 2: Two Devices (Real Multi-Room Audio)

### Setup:
- **PC 1** (Server) - Has audio source (music, game, etc.)
- **PC 2** (Receiver) - Will play synced audio

### Network Requirements:
- Both PCs on **same WiFi/network**
- Firewall allows UDP port 5555

### Steps:

#### **On PC 1 (Server):**

```powershell
# Find your IP address
ipconfig

# Look for "IPv4 Address" like: 192.168.1.100
```

**Using GUI:**
1. Launch: `python syncwave_app.py`
2. **Server Tab:**
   - IP: `192.168.1.101` (PC 2's IP address)
   - Port: `5555`
   - Click **"Start Server"**

**Or Command Line:**
```powershell
python start_server.py
# When prompted: Enter target IP (PC 2's IP)
```

#### **On PC 2 (Receiver):**

**Using GUI:**
1. Launch: `python syncwave_app.py`
2. **Receiver Tab:**
   - Port: `5555`
   - Click **"Start Receiver"**

**Or Command Line:**
```powershell
python receiver_enhanced.py
```

### Expected Result:
- ✅ PC 1 plays audio/music
- ✅ PC 2 speakers play **same audio** with ~100-150ms delay
- ✅ Both stay in perfect sync
- ✅ Latency measurement shows consistent timing

---

## 🎪 Test 3: Multiple Receivers (Party Mode!)

### Setup:
- **1 Server PC**
- **3+ Receiver PCs** (living room, bedroom, kitchen, etc.)

### Method A: Broadcast Mode (Auto-discovery)

#### **Server PC:**
```powershell
python syncwave_app.py
```
**Server Tab:**
- IP: `255.255.255.255`
- Port: `5555`
- ✅ **CHECK** "Broadcast Mode"
- Click **"Start Server"**

#### **All Receiver PCs:**
```powershell
python syncwave_app.py
```
**Receiver Tab:**
- Port: `5555`
- Click **"Start Receiver"**

**Result:** All receivers automatically receive and play synchronized audio! 🎉

---

### Method B: Multi-Target Mode (Specific Devices)

#### **Server PC:**
```powershell
# Stream to 3 specific devices
python start_multi_server.py --targets 192.168.1.101:5555 192.168.1.102:5555 192.168.1.103:5555
```

#### **Each Receiver PC:**
```powershell
python receiver_enhanced.py
```

**Result:** Perfect sync across all specified devices!

---

## 🔍 Troubleshooting Tests

### Test 4: Check Firewall

```powershell
# On receiver PC, test if port is accessible
Test-NetConnection -ComputerName <server-ip> -Port 5555
```

**Expected:** `TcpTestSucceeded : True`

If **False:**
```powershell
# Add firewall rule (run as Administrator)
New-NetFirewallRule -DisplayName "SyncWave" -Direction Inbound -Protocol UDP -LocalPort 5555 -Action Allow
```

---

### Test 5: Check Network Discovery

```powershell
# Server PC - Find your IP
ipconfig | Select-String "IPv4"

# Receiver PC - Test connectivity
ping <server-ip>
```

**Expected:** Reply from IP address

---

### Test 6: Verify Audio Devices

**Using GUI:**
1. Go to **Settings Tab**
2. Check "Audio Device" dropdown
3. Should list your speakers/headphones

**Or Command Line:**
```powershell
python check_devices.py
```

**Expected Output:**
```
Available Audio Output Devices:
  [0] Speakers (Realtek High Definition Audio)
  [1] Headphones (USB Audio Device)
```

---

## 📊 Performance Tests

### Test 7: Latency Measurement

**Run Enhanced Receiver:**
```powershell
python receiver_enhanced.py
```

**Watch for:**
```
Latency: 114ms  ✅ Good (< 150ms)
Latency: 87ms   ✅ Excellent (< 100ms)
Latency: 250ms  ⚠️  High (check network)
```

**Acceptable Latency:**
- ✅ **< 150ms:** Perfect for music/movies
- ⚠️ **150-300ms:** Noticeable but usable
- ❌ **> 300ms:** Check network or reduce WiFi distance

---

### Test 8: Jitter Buffer Tuning

**GUI Method:**
1. **Receiver Tab** → Adjust "Jitter Buffer" slider
2. Try values: `5`, `10`, `20`, `50`

**Results:**
- **5 packets:** Lowest latency, might skip if network unstable
- **10 packets:** Balanced (recommended)
- **20+ packets:** Smoother playback on poor networks

---

### Test 9: Bandwidth Test

**Check Stats Tab in GUI or watch receiver output:**

```
Bitrate: 3079 kbps  → Raw PCM (48kHz stereo)
Bitrate: 128 kbps   → If Opus enabled (future)
```

**Network Requirements:**
- ✅ **Gigabit LAN:** No issues
- ✅ **WiFi 5/6:** Perfect
- ⚠️ **WiFi 4 (2.4GHz):** May need to reduce quality

---

## 🎵 Real-World Test Scenarios

### Scenario 1: Music Streaming
```powershell
# Play music on server PC (Spotify, YouTube, etc.)
# All receivers should play synchronized audio
```

### Scenario 2: Movie Night
```powershell
# Server PC plays movie
# Living room + bedroom receivers play audio in sync
# Perfect for multi-room movie experience
```

### Scenario 3: Gaming
```powershell
# Server PC plays game audio
# Receivers in other rooms hear game sound
# ~114ms latency is acceptable for non-competitive gaming
```

### Scenario 4: Conference/Presentation
```powershell
# Broadcast presentation audio to multiple meeting rooms
# All rooms hear synchronized audio
```

---

## ✅ Success Checklist

After testing, verify:

**Server:**
- [ ] Server starts without errors
- [ ] "Device config: 48000 Hz, 2 channels" appears
- [ ] Headers sent successfully
- [ ] No firewall blocking

**Receiver:**
- [ ] Receives and parses header
- [ ] Audio plays from speakers
- [ ] Latency shows ~100-150ms
- [ ] No crackling/stuttering
- [ ] Audio meters move with sound

**Multi-Device:**
- [ ] Broadcast mode reaches all devices
- [ ] Multi-target mode works
- [ ] All devices stay synchronized
- [ ] Consistent latency across devices

---

## 🐛 Common Issues & Fixes

### Issue: No audio on receiver
**Fix:**
```powershell
# Check audio device
python check_devices.py

# Try different device in GUI Settings Tab
```

### Issue: "Connection refused"
**Fix:**
```powershell
# Check firewall
New-NetFirewallRule -DisplayName "SyncWave" -Direction Inbound -Protocol UDP -LocalPort 5555 -Action Allow

# Verify IP address
ipconfig
```

### Issue: Crackling/stuttering audio
**Fix:**
- Increase jitter buffer (GUI: 10 → 20)
- Check network quality (WiFi signal)
- Close bandwidth-heavy apps

### Issue: High latency (> 300ms)
**Fix:**
- Use wired Ethernet instead of WiFi
- Reduce WiFi distance
- Check for network congestion
- Lower jitter buffer if network is stable

### Issue: Feedback loop (echo)
**Fix:**
- **Never test on same PC** with audio output enabled
- Use `receiver_silent.py` for local testing
- Or test on separate machines

---

## 🚀 Quick Test Commands

**Fastest test (same PC, no audio):**
```powershell
# Terminal 1
python start_server.py

# Terminal 2
python receiver_silent.py
```

**Real multi-room test:**
```powershell
# Server PC
python syncwave_app.py
# Server Tab: Enter receiver IP, Start

# Receiver PC(s)
python syncwave_app.py
# Receiver Tab: Start
```

**Broadcast to all devices:**
```powershell
# Server
python syncwave_app.py
# Enable "Broadcast Mode" ✅

# All Receivers
python receiver_enhanced.py
```

---

## 📈 Expected Performance Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Sample Rate | 48000 Hz | ✅ |
| Channels | 2 (Stereo) | ✅ |
| Latency | 100-150ms | ✅ Excellent |
| Bitrate (Raw) | ~3000 kbps | ✅ |
| Bitrate (Opus) | ~128 kbps | 🔜 Future |
| Packet Loss | 0% | ✅ Target |
| Jitter Buffer | 10 packets | ✅ Default |

---

**🎉 Happy Testing! Your multi-room audio sync should work flawlessly!**
