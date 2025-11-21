# 🚀 SyncWave - Build & Deploy Guide

## Creating a Standalone Desktop Application

Follow these steps to create a **professional, distributable Windows application** that can be installed on any PC.

---

## 📋 Prerequisites

✅ Python 3.11+ installed  
✅ CMake installed (for Opus support)  
✅ Visual Studio Build Tools (for Rust)  
✅ All dependencies installed  

---

## 🔨 Step-by-Step Build Process

### Step 1: Install Dependencies

```powershell
# Navigate to project directory
cd D:\myStuff\Project

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install all requirements
pip install -r requirements.txt
pip install pyinstaller
```

### Step 2: Build Rust Core

```powershell
# Build the high-performance audio core
maturin develop --release

# Verify build
python -c "import syncwave_core; print('✅ Rust core ready!')"
```

### Step 3: Test the GUI Application

```powershell
# Run the application to verify it works
python syncwave_app.py
```

**Test checklist:**
- [ ] Application window opens
- [ ] Server tab configurable
- [ ] Receiver tab configurable
- [ ] Settings tab shows devices
- [ ] Can start/stop server
- [ ] Can start/stop receiver

### Step 4: Build Standalone Executable

```powershell
# Run the automated build script
python build_app.py
```

**This will:**
1. ✅ Check all requirements
2. ✅ Build Rust core (if needed)
3. ✅ Package Python code
4. ✅ Include all dependencies
5. ✅ Create `SyncWave.exe` in `dist/` folder

### Step 5: Test the Executable

```powershell
# Run the standalone executable
.\dist\SyncWave.exe
```

**The executable includes:**
- ✅ All Python libraries
- ✅ Rust audio core (syncwave_core.pyd)
- ✅ CustomTkinter UI assets
- ✅ PyAudio binaries
- ✅ Configuration system

---

## 📦 What You Get

After building, you'll have:

```
dist/
└── SyncWave.exe    (20-40 MB standalone executable)
```

### ✨ Features of the Executable:

**✅ Zero Dependencies**  
- No Python installation required
- No library installation needed
- Works on any Windows 10/11 PC

**✅ Portable**  
- Single EXE file
- Copy to USB drive
- Run from anywhere

**✅ Professional**  
- Windows application
- No console window
- Modern GUI
- Settings persistence

---

## 🎯 Distribution Options

### Option 1: Simple Copy

```powershell
# Copy to target machine
Copy-Item ".\dist\SyncWave.exe" -Destination "\\TargetPC\C$\Program Files\SyncWave\"

# Create desktop shortcut manually
```

### Option 2: Create Installer (Advanced)

Use **Inno Setup** or **NSIS** to create a professional installer:

```powershell
# Install Inno Setup from: https://jrsoftware.org/isinfo.php

# Create installer script (syncwave_installer.iss)
```

**Example Inno Setup Script:**
```iss
[Setup]
AppName=SyncWave
AppVersion=2.0
DefaultDirName={pf}\SyncWave
OutputBaseFilename=SyncWave_Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\SyncWave.exe"; DestDir: "{app}"

[Icons]
Name: "{commondesktop}\SyncWave"; Filename: "{app}\SyncWave.exe"
Name: "{group}\SyncWave"; Filename: "{app}\SyncWave.exe"
```

### Option 3: Microsoft Store (Professional)

Package as **MSIX** for Microsoft Store distribution:
```powershell
# Requires Windows SDK
makeappx pack /d .\dist /p SyncWave.msix
```

---

## 🎨 Customization

### Add Custom Icon

1. Create or download an icon file
2. Save as `icon.ico` in project root
3. Rebuild:
```powershell
python build_app.py
```

### Change App Name

Edit `syncwave.spec`:
```python
name='YourAppName',  # Change this line
```

### Add Splash Screen

Add to `syncwave.spec`:
```python
splash = Splash(
    'splash.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(10, 50),
    text_size=12,
    text_color='black'
)
```

---

## 📊 Build Optimization

### Reduce File Size

```powershell
# Use UPX compression (already enabled in spec file)
# Final size: ~20-30 MB

# Without UPX: ~50-60 MB
# With UPX: ~20-30 MB
```

### Faster Builds

```powershell
# Skip UPX compression for faster development builds
pyinstaller syncwave.spec --clean --noconfirm --noupx
```

---

## 🐛 Troubleshooting Build Issues

### Issue: "CMake Error: Compatibility with CMake < 3.5 has been removed"

**Solution:**
This occurs because the `audiopus` library requires an older version of CMake than what might be installed on your system.
👉 **See [TROUBLESHOOTING_OPUS_BUILD.md](TROUBLESHOOTING_OPUS_BUILD.md) for the complete fix.**

### Issue: "syncwave_core.pyd not found"

**Solution:**
```powershell
# Rebuild Rust core
maturin develop --release

# Verify location
python -c "import syncwave_core; print(syncwave_core.__file__)"

# Update syncwave.spec datas path if needed
```

### Issue: "CustomTkinter assets missing"

**Solution:**
```powershell
# Reinstall CustomTkinter
pip install --force-reinstall customtkinter
```

### Issue: "PyAudio DLL not found"

**Solution:**
```powershell
# Use PyAudioWPatch instead
pip uninstall pyaudio
pip install pyaudiowpatch
```

### Issue: Build succeeds but EXE crashes

**Solution:**
```powershell
# Test with console window enabled
# Edit syncwave.spec: console=True

# Rebuild and check error messages
python build_app.py
.\dist\SyncWave.exe
```

---

## ✅ Deployment Checklist

Before distributing your application:

**Testing:**
- [ ] Test on clean Windows 10 VM (no Python)
- [ ] Test on Windows 11
- [ ] Test server functionality
- [ ] Test receiver functionality
- [ ] Test settings persistence
- [ ] Test with firewall enabled

**Documentation:**
- [ ] Create user manual
- [ ] Include README_APP.md
- [ ] Add license file
- [ ] Create quick start guide

**Packaging:**
- [ ] Custom icon added
- [ ] Version number updated
- [ ] About dialog completed
- [ ] Installer tested (if created)

**Distribution:**
- [ ] Upload to file host / website
- [ ] Create download page
- [ ] Add to GitHub releases
- [ ] Submit to Microsoft Store (optional)

---

## 🎉 Success!

You now have a **professional desktop application** ready for distribution!

```
Your Application:
📍 Location: D:\myStuff\Project\dist\SyncWave.exe
📦 Size: ~20-40 MB
🎯 Target: Windows 10/11 (64-bit)
✨ Status: Production Ready
```

### Next Steps:

1. **Test** on different machines
2. **Distribute** to users
3. **Collect** feedback
4. **Iterate** and improve

---

## 💡 Pro Tips

**For Development:**
```powershell
# Quick test without full build
python syncwave_app.py
```

**For Distribution:**
```powershell
# Full optimized build
python build_app.py
```

**For Updates:**
```powershell
# Rebuild only changed files
pyinstaller syncwave.spec --noconfirm
```

**For Debugging:**
```powershell
# Enable console output
# Edit syncwave.spec: console=True
python build_app.py
```

---

**🎵 Happy Building! Your professional audio sync application is ready to ship!**
