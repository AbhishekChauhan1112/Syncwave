# 🔧 Troubleshooting: Building Opus Support on Windows

If you encounter a build error related to **CMake** when running `maturin develop --release`, specifically regarding `audiopus_sys` and CMake version compatibility, follow this guide.

## 🔴 The Error

When building the Rust core with Opus compression enabled, you might see an error like this:

```
error: failed to run custom build command for `audiopus_sys v0.2.2`
...
CMake Error at CMakeLists.txt:1 (cmake_minimum_required):
  Compatibility with CMake < 3.5 has been removed from CMake.
```

## 🔍 The Cause

The `audiopus_sys` crate (which provides bindings to the Opus audio library) uses a build script with an older CMake configuration. If you have a very new version of CMake installed (e.g., CMake 4.x), it will reject the older configuration, causing the build to fail.

## ✅ The Solution

To fix this, we need to use a compatible version of CMake (version 3.x) specifically for this build.

### Step 1: Install Compatible CMake via Pip

Downgrade the Python `cmake` package to version 3.25.0, which includes a compatible CMake binary.

```powershell
pip install "cmake==3.25.0"
```

### Step 2: Locate the CMake Binary

Find where the `cmake` package installed its binary. You can do this by running:

```powershell
python -c "import cmake; print(cmake.CMAKE_BIN_DIR)"
```

*Typically, it is located at:*
`C:\Users\<YourUser>\AppData\Roaming\Python\Python311\site-packages\cmake\data\bin`

### Step 3: Build with the Correct CMake

Set the `CMAKE` environment variable to point to the compatible binary and run the build command.

**PowerShell Command (One-Liner):**

```powershell
$env:CMAKE = "C:\Users\abhis\AppData\Roaming\Python\Python311\site-packages\cmake\data\bin\cmake.exe"; maturin develop --release
```

> **Note:** Replace the path above with the actual path found in Step 2 if it differs.

### Step 4: Verify Success

If successful, you will see:
```
📦 Built wheel for CPython 3.11 ...
🛠 Installed Project-0.1.0
```

You can now run the application with full Opus compression support!
