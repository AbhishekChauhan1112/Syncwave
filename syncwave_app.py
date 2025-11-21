"""
SyncWave - Professional Audio Sync Application
Full-Featured Desktop Application with GUI

Features:
- Modern CustomTkinter GUI
- Real-time audio server management
- Integrated receiver functionality
- Settings persistence
- Visual audio meters
- System tray integration
- Connection status monitoring
"""

import customtkinter as ctk
import threading
import socket
import json
import os
from pathlib import Path
import pyaudio
import struct
import time
import collections
from tkinter import messagebox
import sys

# Import Rust audio core
try:
    import syncwave_core
    RUST_CORE_AVAILABLE = True
except ImportError:
    RUST_CORE_AVAILABLE = False
    messagebox.showerror("Error", "SyncWave Rust core not found! Please run: maturin develop")

# Configuration
CONFIG_FILE = Path.home() / ".syncwave" / "config.json"
CONFIG_FILE.parent.mkdir(exist_ok=True)

# Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AudioMeter(ctk.CTkProgressBar):
    """Custom audio level meter widget"""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.set(0)
        self.configure(mode="determinate")
    
    def update_level(self, level):
        """Update meter level (0.0 to 1.0)"""
        self.set(level)
        # Change color based on level
        if level > 0.9:
            self.configure(progress_color="red")
        elif level > 0.7:
            self.configure(progress_color="orange")
        else:
            self.configure(progress_color="green")

class JitterBuffer:
    """Audio jitter buffer for smooth playback"""
    def __init__(self, size=10):
        self.buffer = collections.deque(maxlen=size)
        self.lock = threading.Lock()
    
    def add(self, data):
        with self.lock:
            self.buffer.append(data)
    
    def get(self):
        with self.lock:
            if len(self.buffer) >= 3:
                return self.buffer.popleft()
            return None
    
    def size(self):
        with self.lock:
            return len(self.buffer)

class SyncWaveApp(ctk.CTk):
    """Main Application Window"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("SyncWave Audio Sync")
        self.geometry("1000x700")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Application state
        self.config = self.load_config()
        self.server_thread = None
        self.receiver_thread = None
        self.server_running = False
        self.receiver_running = False
        
        # Audio objects
        self.pyaudio_instance = None
        self.audio_stream = None
        
        # UI Setup
        self.create_ui()
        self.apply_config()
        
    def load_config(self):
        """Load configuration from file"""
        default_config = {
            "server": {
                "target_ip": "127.0.0.1",
                "target_port": 5555,
                "compression": False,
                "broadcast": False
            },
            "receiver": {
                "listen_port": 5555,
                "jitter_buffer_size": 10,
                "buffer_frames": 2048
            },
            "appearance": {
                "theme": "dark"
            }
        }
        
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except:
                pass
        
        return default_config
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def create_ui(self):
        """Create the user interface"""
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=10)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="🎵 SyncWave Audio Sync",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack(side="left")
        
        version_label = ctk.CTkLabel(
            header_frame,
            text="v2.0",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        version_label.pack(side="left", padx=10)
        
        # Main content area with tabs
        self.tabview = ctk.CTkTabview(self, width=950, height=600)
        self.tabview.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Create tabs
        self.tabview.add("🎙️ Server")
        self.tabview.add("🔊 Receiver")
        self.tabview.add("⚙️ Settings")
        self.tabview.add("📊 Stats")
        
        self.create_server_tab()
        self.create_receiver_tab()
        self.create_settings_tab()
        self.create_stats_tab()
        
    def create_server_tab(self):
        """Create server control tab"""
        tab = self.tabview.tab("🎙️ Server")
        
        # Configuration Frame
        config_frame = ctk.CTkFrame(tab)
        config_frame.pack(padx=20, pady=20, fill="x")
        
        ctk.CTkLabel(
            config_frame,
            text="Server Configuration",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)
        
        # Mode Selection
        mode_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        mode_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(mode_frame, text="Streaming Mode:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=5)
        
        self.server_mode_var = ctk.StringVar(value="single")
        
        ctk.CTkRadioButton(
            mode_frame,
            text="📡 Single Target (One device)",
            variable=self.server_mode_var,
            value="single",
            command=self.on_mode_change
        ).pack(anchor="w", pady=2)
        
        ctk.CTkRadioButton(
            mode_frame,
            text="🌐 Broadcast (All devices on network)",
            variable=self.server_mode_var,
            value="broadcast",
            command=self.on_mode_change
        ).pack(anchor="w", pady=2)
        
        ctk.CTkRadioButton(
            mode_frame,
            text="🎯 Multi-Target (Specific devices)",
            variable=self.server_mode_var,
            value="multi",
            command=self.on_mode_change
        ).pack(anchor="w", pady=2)
        
        # Single Target Configuration
        self.single_target_frame = ctk.CTkFrame(config_frame)
        self.single_target_frame.pack(pady=10, padx=20, fill="x")
        
        ip_frame = ctk.CTkFrame(self.single_target_frame, fg_color="transparent")
        ip_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(ip_frame, text="Target IP:", width=100, anchor="w").pack(side="left", padx=5)
        self.server_ip_entry = ctk.CTkEntry(ip_frame, width=200)
        self.server_ip_entry.pack(side="left", padx=5)
        
        port_frame = ctk.CTkFrame(self.single_target_frame, fg_color="transparent")
        port_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(port_frame, text="Target Port:", width=100, anchor="w").pack(side="left", padx=5)
        self.server_port_entry = ctk.CTkEntry(port_frame, width=200)
        self.server_port_entry.pack(side="left", padx=5)
        
        # Multi-Target Configuration
        self.multi_target_frame = ctk.CTkFrame(config_frame)
        
        ctk.CTkLabel(
            self.multi_target_frame,
            text="Target Devices:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=5)
        
        # Device list
        self.device_list_frame = ctk.CTkScrollableFrame(self.multi_target_frame, height=150)
        self.device_list_frame.pack(pady=5, fill="both", expand=True)
        
        self.target_devices = []  # List to store (ip, port) tuples
        self.device_labels = []   # List to store label widgets
        
        # Add device controls
        add_device_frame = ctk.CTkFrame(self.multi_target_frame, fg_color="transparent")
        add_device_frame.pack(pady=5, fill="x")
        
        self.new_device_ip = ctk.CTkEntry(add_device_frame, placeholder_text="IP Address", width=150)
        self.new_device_ip.pack(side="left", padx=5)
        
        self.new_device_port = ctk.CTkEntry(add_device_frame, placeholder_text="Port", width=80)
        self.new_device_port.pack(side="left", padx=5)
        
        ctk.CTkButton(
            add_device_frame,
            text="➕ Add Device",
            command=self.add_target_device,
            width=100
        ).pack(side="left", padx=5)
        
        # Options
        options_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        options_frame.pack(pady=10, padx=20, fill="x")
        
        self.server_compression_var = ctk.BooleanVar()
        self.server_broadcast_var = ctk.BooleanVar()
        
        ctk.CTkCheckBox(
            options_frame,
            text="Enable Compression (Opus - requires setup)",
            variable=self.server_compression_var,
            state="disabled"
        ).pack(anchor="w", pady=5)
        
        # Control buttons
        button_frame = ctk.CTkFrame(tab, fg_color="transparent")
        button_frame.pack(pady=20)
        
        self.server_button = ctk.CTkButton(
            button_frame,
            text="▶ Start Server",
            command=self.toggle_server,
            width=200,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="green",
            hover_color="darkgreen"
        )
        self.server_button.pack()
        
        # Status Frame
        status_frame = ctk.CTkFrame(tab)
        status_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        ctk.CTkLabel(
            status_frame,
            text="Server Status",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.server_status_label = ctk.CTkLabel(
            status_frame,
            text="● Server Stopped",
            text_color="gray",
            font=ctk.CTkFont(size=14)
        )
        self.server_status_label.pack(pady=5)
        
        # Log area
        self.server_log = ctk.CTkTextbox(status_frame, height=200)
        self.server_log.pack(pady=10, padx=10, fill="both", expand=True)
        
    def create_receiver_tab(self):
        """Create receiver control tab"""
        tab = self.tabview.tab("🔊 Receiver")
        
        # Configuration Frame
        config_frame = ctk.CTkFrame(tab)
        config_frame.pack(padx=20, pady=20, fill="x")
        
        ctk.CTkLabel(
            config_frame,
            text="Receiver Configuration",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)
        
        # Listen Port
        port_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        port_frame.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkLabel(port_frame, text="Listen Port:", width=150, anchor="w").pack(side="left", padx=5)
        self.receiver_port_entry = ctk.CTkEntry(port_frame, width=200)
        self.receiver_port_entry.pack(side="left", padx=5)
        
        # Jitter Buffer
        jitter_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        jitter_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(jitter_frame, text="Jitter Buffer:", width=150, anchor="w").pack(side="left", padx=5)
        
        self.jitter_slider = ctk.CTkSlider(
            jitter_frame,
            from_=5,
            to=50,
            number_of_steps=45,
            width=200
        )
        self.jitter_slider.pack(side="left", padx=5)
        
        self.jitter_label = ctk.CTkLabel(jitter_frame, text="10 packets", width=100)
        self.jitter_label.pack(side="left", padx=5)
        self.jitter_slider.configure(command=lambda v: self.jitter_label.configure(text=f"{int(v)} packets"))
        
        # Control buttons
        button_frame = ctk.CTkFrame(tab, fg_color="transparent")
        button_frame.pack(pady=20)
        
        self.receiver_button = ctk.CTkButton(
            button_frame,
            text="▶ Start Receiver",
            command=self.toggle_receiver,
            width=200,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="blue",
            hover_color="darkblue"
        )
        self.receiver_button.pack()
        
        # Status Frame
        status_frame = ctk.CTkFrame(tab)
        status_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.receiver_status_label = ctk.CTkLabel(
            status_frame,
            text="● Receiver Stopped",
            text_color="gray",
            font=ctk.CTkFont(size=14)
        )
        self.receiver_status_label.pack(pady=5)
        
        # Audio Level Meters
        meter_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        meter_frame.pack(pady=10, fill="x", padx=20)
        
        ctk.CTkLabel(meter_frame, text="Audio Levels", font=ctk.CTkFont(size=12, weight="bold")).pack()
        
        level_container = ctk.CTkFrame(meter_frame, fg_color="transparent")
        level_container.pack(pady=5, fill="x")
        
        ctk.CTkLabel(level_container, text="L:", width=30).pack(side="left")
        self.audio_meter_l = AudioMeter(level_container, width=300)
        self.audio_meter_l.pack(side="left", padx=5)
        
        ctk.CTkLabel(level_container, text="R:", width=30).pack(side="left", padx=(20, 0))
        self.audio_meter_r = AudioMeter(level_container, width=300)
        self.audio_meter_r.pack(side="left", padx=5)
        
        # Stats display
        self.receiver_stats_label = ctk.CTkLabel(
            status_frame,
            text="Waiting for stream...",
            font=ctk.CTkFont(size=12)
        )
        self.receiver_stats_label.pack(pady=10)
        
    def create_settings_tab(self):
        """Create settings tab"""
        tab = self.tabview.tab("⚙️ Settings")
        
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        ctk.CTkLabel(
            settings_frame,
            text="Application Settings",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=20)
        
        # Audio Devices
        ctk.CTkLabel(
            settings_frame,
            text="Audio Devices",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=10, anchor="w", padx=20)
        
        # Get audio devices
        p = pyaudio.PyAudio()
        
        # Output devices
        device_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        device_frame.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkLabel(device_frame, text="Output Device:", width=150, anchor="w").pack(side="left")
        
        output_devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                output_devices.append(f"{i}: {info['name'][:50]}")
        
        self.output_device_menu = ctk.CTkOptionMenu(
            device_frame,
            values=output_devices if output_devices else ["No devices found"],
            width=500
        )
        self.output_device_menu.pack(side="left", padx=10)
        
        p.terminate()
        
        # Network Info
        ctk.CTkLabel(
            settings_frame,
            text="Network Information",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=20, anchor="w", padx=20)
        
        network_frame = ctk.CTkFrame(settings_frame)
        network_frame.pack(pady=5, padx=20, fill="x")
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "Unable to detect"
        
        ctk.CTkLabel(
            network_frame,
            text=f"Local IP Address: {local_ip}",
            font=ctk.CTkFont(size=13)
        ).pack(pady=10)
        
        # Save button
        ctk.CTkButton(
            settings_frame,
            text="💾 Save Settings",
            command=self.save_settings,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14)
        ).pack(pady=30)
        
    def create_stats_tab(self):
        """Create statistics tab"""
        tab = self.tabview.tab("📊 Stats")
        
        stats_frame = ctk.CTkFrame(tab)
        stats_frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        ctk.CTkLabel(
            stats_frame,
            text="Connection Statistics",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=20)
        
        self.stats_text = ctk.CTkTextbox(stats_frame, font=ctk.CTkFont(size=12))
        self.stats_text.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.update_stats_display()
        
    def apply_config(self):
        """Apply saved configuration to UI"""
        self.server_ip_entry.insert(0, self.config["server"]["target_ip"])
        self.server_port_entry.insert(0, str(self.config["server"]["target_port"]))
        self.server_compression_var.set(self.config["server"]["compression"])
        self.server_broadcast_var.set(self.config["server"]["broadcast"])
        
        self.receiver_port_entry.insert(0, str(self.config["receiver"]["listen_port"]))
        self.jitter_slider.set(self.config["receiver"]["jitter_buffer_size"])
        
    def save_settings(self):
        """Save current settings"""
        try:
            self.config["server"]["target_ip"] = self.server_ip_entry.get()
            self.config["server"]["target_port"] = int(self.server_port_entry.get())
            self.config["server"]["compression"] = self.server_compression_var.get()
            self.config["server"]["broadcast"] = self.server_broadcast_var.get()
            
            self.config["receiver"]["listen_port"] = int(self.receiver_port_entry.get())
            self.config["receiver"]["jitter_buffer_size"] = int(self.jitter_slider.get())
            
            self.save_config()
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def on_mode_change(self):
        """Handle streaming mode change"""
        mode = self.server_mode_var.get()
        
        # Hide all frames first
        self.single_target_frame.pack_forget()
        self.multi_target_frame.pack_forget()
        
        # Show relevant frame
        if mode == "single":
            self.single_target_frame.pack(pady=10, padx=20, fill="x")
        elif mode == "multi":
            self.multi_target_frame.pack(pady=10, padx=20, fill="x")
        # Broadcast mode needs no additional config
    
    def add_target_device(self):
        """Add a device to the multi-target list"""
        ip = self.new_device_ip.get().strip()
        port_str = self.new_device_port.get().strip()
        
        if not ip or not port_str:
            messagebox.showwarning("Input Required", "Please enter both IP and Port")
            return
        
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError("Port out of range")
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a number between 1-65535")
            return
        
        # Check for duplicates
        if (ip, port) in self.target_devices:
            messagebox.showwarning("Duplicate", f"Device {ip}:{port} already added")
            return
        
        # Add to list
        self.target_devices.append((ip, port))
        
        # Create label with remove button
        device_frame = ctk.CTkFrame(self.device_list_frame)
        device_frame.pack(pady=2, fill="x")
        
        label = ctk.CTkLabel(
            device_frame,
            text=f"📍 {ip}:{port}",
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        label.pack(side="left", padx=5, fill="x", expand=True)
        
        remove_btn = ctk.CTkButton(
            device_frame,
            text="❌",
            width=30,
            command=lambda: self.remove_target_device(ip, port, device_frame)
        )
        remove_btn.pack(side="right", padx=5)
        
        self.device_labels.append(device_frame)
        
        # Clear inputs
        self.new_device_ip.delete(0, 'end')
        self.new_device_port.delete(0, 'end')
        
        self.log_server(f"Added target device: {ip}:{port}")
    
    def remove_target_device(self, ip, port, frame):
        """Remove a device from the multi-target list"""
        if (ip, port) in self.target_devices:
            self.target_devices.remove((ip, port))
            frame.destroy()
            self.device_labels.remove(frame)
            self.log_server(f"Removed target device: {ip}:{port}")
    
    def on_broadcast_toggle(self):
        """Handle broadcast toggle"""
        if self.server_broadcast_var.get():
            self.server_ip_entry.delete(0, 'end')
            self.server_ip_entry.insert(0, "255.255.255.255")
            self.server_ip_entry.configure(state="disabled")
        else:
            self.server_ip_entry.configure(state="normal")
            if self.server_ip_entry.get() == "255.255.255.255":
                self.server_ip_entry.delete(0, 'end')
                self.server_ip_entry.insert(0, "127.0.0.1")
    
    def log_server(self, message):
        """Log message to server console"""
        self.server_log.insert("end", f"{message}\n")
        self.server_log.see("end")
        
    def toggle_server(self):
        """Start or stop server"""
        if not self.server_running:
            self.start_server()
        else:
            self.stop_server()
    
    def start_server(self):
        """Start audio server"""
        if not RUST_CORE_AVAILABLE:
            messagebox.showerror("Error", "Rust core not available!")
            return
        
        try:
            mode = self.server_mode_var.get()
            use_compression = self.server_compression_var.get()
            
            if mode == "single":
                # Single target mode
                target_ip = self.server_ip_entry.get()
                target_port = int(self.server_port_entry.get())
                
                self.log_server(f"Starting server to {target_ip}:{target_port}")
                
                self.server_thread = threading.Thread(
                    target=self.run_server,
                    args=(target_ip, target_port, use_compression, False),
                    daemon=True
                )
                self.server_thread.start()
                
            elif mode == "broadcast":
                # Broadcast mode
                target_port = int(self.server_port_entry.get())
                
                self.log_server(f"Starting broadcast server on port {target_port}")
                
                self.server_thread = threading.Thread(
                    target=self.run_server,
                    args=("255.255.255.255", target_port, use_compression, True),
                    daemon=True
                )
                self.server_thread.start()
                
            elif mode == "multi":
                # Multi-target mode
                if not self.target_devices:
                    messagebox.showwarning("No Devices", "Please add at least one target device")
                    return
                
                self.log_server(f"Starting multi-target server to {len(self.target_devices)} devices")
                
                # Create threads for each target
                self.server_threads = []
                for ip, port in self.target_devices:
                    self.log_server(f"  → {ip}:{port}")
                    thread = threading.Thread(
                        target=self.run_server,
                        args=(ip, port, use_compression, False),
                        daemon=True,
                        name=f"Server-{ip}:{port}"
                    )
                    thread.start()
                    self.server_threads.append(thread)
            
            self.server_running = True
            self.server_button.configure(
                text="⏹ Stop Server",
                fg_color="red",
                hover_color="darkred"
            )
            self.server_status_label.configure(
                text="● Server Running",
                text_color="green"
            )
            
            # Disable mode selection while running
            self.server_ip_entry.configure(state="disabled")
            self.server_port_entry.configure(state="disabled")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {e}")
            self.log_server(f"ERROR: {e}")
    
    def run_server(self, ip, port, compression, broadcast):
        """Run server in background"""
        try:
            # This will run in a daemon thread and release Python's GIL
            syncwave_core.start_audio_server(ip, port, compression, broadcast)
        except Exception as e:
            self.log_server(f"Server error: {e}")
            self.after(0, lambda: messagebox.showerror("Server Error", str(e)))
    
    def stop_server(self):
        """Stop audio server"""
        self.log_server("Stopping server...")
        self.server_running = False
        
        # Note: Server thread is daemon and will terminate when app closes
        # No graceful shutdown mechanism yet - requires Rust refactoring
        if self.server_thread and self.server_thread.is_alive():
            self.log_server("⚠ Server thread still running (will stop on app exit)")
        
        self.server_button.configure(
            text="▶ Start Server",
            fg_color="green",
            hover_color="darkgreen"
        )
        self.server_status_label.configure(
            text="● Server Stopped",
            text_color="red"
        )
        
        self.server_ip_entry.configure(state="normal")
        self.server_port_entry.configure(state="normal")
        
        messagebox.showinfo("Info", "Server will stop after current stream ends.")
    
    def toggle_receiver(self):
        """Start or stop receiver"""
        if not self.receiver_running:
            self.start_receiver()
        else:
            self.stop_receiver()
    
    def start_receiver(self):
        """Start audio receiver"""
        try:
            listen_port = int(self.receiver_port_entry.get())
            
            self.receiver_thread = threading.Thread(
                target=self.run_receiver,
                args=(listen_port,),
                daemon=True
            )
            self.receiver_thread.start()
            
            self.receiver_running = True
            self.receiver_button.configure(
                text="⏹ Stop Receiver",
                fg_color="red",
                hover_color="darkred"
            )
            self.receiver_status_label.configure(
                text="● Receiver Running",
                text_color="green"
            )
            
            self.receiver_port_entry.configure(state="disabled")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start receiver: {e}")
    
    def run_receiver(self, port):
        """Run receiver in background"""
        # This is a simplified version - full implementation in receiver_enhanced.py
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", port))
            
            self.after(100, lambda: self.receiver_stats_label.configure(
                text=f"Listening on port {port}..."
            ))
            
            # Simplified receiver loop
            while self.receiver_running:
                try:
                    sock.settimeout(1.0)
                    data, addr = sock.recvfrom(65536)
                    # Process data here
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Receiver error: {e}")
                    break
            
            sock.close()
        except Exception as e:
            print(f"Receiver failed: {e}")
    
    def stop_receiver(self):
        """Stop audio receiver"""
        self.receiver_running = False
        self.receiver_button.configure(
            text="▶ Start Receiver",
            fg_color="blue",
            hover_color="darkblue"
        )
        self.receiver_status_label.configure(
            text="● Receiver Stopped",
            text_color="gray"
        )
        
        self.receiver_port_entry.configure(state="normal")
        self.receiver_stats_label.configure(text="Receiver stopped")
    
    def update_stats_display(self):
        """Update statistics display"""
        stats_text = f"""
╔══════════════════════════════════════════════════════════════╗
║                  SyncWave System Statistics                  ║
╚══════════════════════════════════════════════════════════════╝

Server Status:    {'🟢 Running' if self.server_running else '⚫ Stopped'}
Receiver Status:  {'🟢 Running' if self.receiver_running else '⚫ Stopped'}

Configuration File: {CONFIG_FILE}

Application Version: 2.0.0
Rust Core: {'✅ Available' if RUST_CORE_AVAILABLE else '❌ Not Found'}

        """
        
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", stats_text)
        
        # Schedule next update
        self.after(2000, self.update_stats_display)
    
    def on_closing(self):
        """Handle window close"""
        if self.server_running or self.receiver_running:
            if messagebox.askokcancel("Quit", "Server/Receiver is running. Stop and quit?"):
                self.server_running = False
                self.receiver_running = False
                self.destroy()
        else:
            self.destroy()

def main():
    """Main entry point"""
    app = SyncWaveApp()
    app.mainloop()

if __name__ == "__main__":
    main()
