"""
Build Script for SyncWave Desktop Application
Creates a standalone executable with all dependencies
"""

import subprocess
import sys
import shutil
from pathlib import Path

def check_requirements():
    """Check if all build requirements are installed"""
    print("🔍 Checking build requirements...")
    
    requirements = ['pyinstaller', 'customtkinter', 'pyaudio']
    missing = []
    
    for req in requirements:
        try:
            __import__(req.replace('-', '_'))
            print(f"  ✅ {req}")
        except ImportError:
            print(f"  ❌ {req} - MISSING")
            missing.append(req)
    
    if missing:
        print(f"\n⚠️  Missing requirements: {', '.join(missing)}")
        print(f"   Run: pip install {' '.join(missing)}")
        return False
    
    return True

def build_rust_core():
    """Build the Rust core module"""
    print("\n🔨 Building Rust core module...")
    
    try:
        result = subprocess.run(
            ['maturin', 'develop', '--release'],
            capture_output=True,
            text=True,
            check=True
        )
        print("  ✅ Rust core built successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Rust build failed: {e}")
        print(e.stdout)
        print(e.stderr)
        return False
    except FileNotFoundError:
        print("  ❌ Maturin not found. Install with: pip install maturin")
        return False

def create_icon():
    """Create application icon if not exists"""
    icon_path = Path("icon.ico")
    if not icon_path.exists():
        print("\n💡 No icon.ico found - application will use default icon")
        print("   Create an icon.ico file to customize the application icon")

def build_executable():
    """Build the executable using PyInstaller"""
    print("\n📦 Building executable...")
    
    try:
        # Clean previous builds
        if Path("build").exists():
            shutil.rmtree("build")
        if Path("dist").exists():
            shutil.rmtree("dist")
        
        # Build with PyInstaller
        result = subprocess.run(
            ['pyinstaller', 'syncwave.spec', '--clean'],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("  ✅ Executable built successfully!")
        print(f"\n🎉 SyncWave.exe created in: {Path('dist').absolute()}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Build failed: {e}")
        print(e.stdout)
        print(e.stderr)
        return False

def main():
    """Main build process"""
    print("=" * 60)
    print("  SyncWave Desktop Application - Build Script")
    print("=" * 60)
    
    # Step 1: Check requirements
    if not check_requirements():
        print("\n❌ Build aborted: Missing requirements")
        sys.exit(1)
    
    # Step 2: Build Rust core
    if not build_rust_core():
        print("\n❌ Build aborted: Rust core build failed")
        sys.exit(1)
    
    # Step 3: Create icon
    create_icon()
    
    # Step 4: Build executable
    if not build_executable():
        print("\n❌ Build failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("  🎉 BUILD COMPLETE!")
    print("=" * 60)
    print("\nYour standalone application is ready:")
    print(f"  📍 Location: {Path('dist/SyncWave.exe').absolute()}")
    print("\nYou can:")
    print("  • Run SyncWave.exe directly")
    print("  • Copy it to any Windows machine")
    print("  • Create a desktop shortcut")
    print("  • Distribute to users")
    print("\n💡 No Python installation required on target machines!")
    print("=" * 60)

if __name__ == "__main__":
    main()
