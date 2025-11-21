import syncwave_core

print("Asking Rust to find audio devices...")
try:
    devices = syncwave_core.get_output_devices()

    print(f"\nFound {len(devices)} devices:")
    print("-" * 30)
    for device in devices:
        print(f"🔊 {device}")

except Exception as e:
    print(f"❌ Error: {e}")