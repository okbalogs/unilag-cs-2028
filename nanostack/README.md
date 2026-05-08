# Nano-Stack

**Build Android apps without Java, Gradle, or Android Studio.**

Nano-Stack is a lightweight Python-based toolchain that lets you write
Android apps in a simple declarative language called NanoCode (`.nano` files)
and compiles them into real, installable APKs in under 5 seconds using less
than 100 MB of RAM.

---

## The Problem

Traditional Android development requires:

| Tool            | Size     | RAM Usage |
|-----------------|----------|-----------|
| Android Studio  | 1.2 GB   | 2–4 GB    |
| JDK 17+         | 300 MB   | 200 MB    |
| Gradle          | 120 MB   | 500 MB    |
| SDK Platform    | 800 MB   | —         |
| **Total**       | **~2.4 GB** | **~3 GB** |

First build time: 3–10 minutes. Every subsequent build: 30–90 seconds.

Nano-Stack replaces all of that:

| Tool            | Size    | RAM Usage |
|-----------------|---------|-----------|
| Python 3.8+     | ~30 MB  | ~30 MB    |
| Nano-Stack      | ~5 MB   | ~20 MB    |
| runner.apk      | ~3 MB   | included  |
| **Total**       | **~38 MB** | **~50 MB** |

Build time: **under 5 seconds**. No internet required after install.

---

## Installation

```bash
pip install nanostack
```

---

## Quick Start

```bash
# 1. Create a new project
nano new MyApp

# 2. Edit app.nano
cd MyApp
# ... edit app.nano with your favourite text editor

# 3. Check for errors
nano check

# 4. Build the APK
nano build

# 5. Deploy to a connected Android device
nano run
```

---

## NanoCode Example — Login Screen

```nano
app:
  name: LoginApp
  version: 1.0

screen: LoginScreen
  background: "#FFFFFF"

  text:
    value: "Welcome Back"
    size: 28
    bold: true
    align: center
    color: "#111111"

  input:
    id: username_field
    hint: "Enter your email"
    type: email

  input:
    id: password_field
    hint: "Enter your password"
    type: password

  button:
    label: "Login"
    color: "#4A90E2"
    on_click:
      - validate: [username_field, password_field]
      - navigate: HomeScreen

  link:
    label: "Forgot Password?"
    navigate: ResetScreen

screen: HomeScreen
  background: "#F5F5F5"

  text:
    value: "You are logged in"
    size: 22
    bold: true

  button:
    label: "Logout"
    color: "#FF4444"
    on_click:
      - navigate: LoginScreen
```

---

## Supported Native Modules

| Module        | What it Does                              | Permission Required |
|---------------|-------------------------------------------|---------------------|
| `bluetooth`   | Scan, connect, send/receive data          | BLUETOOTH_SCAN, BLUETOOTH_CONNECT |
| `camera`      | Take photos and videos                    | CAMERA              |
| `storage`     | Read/write files to device storage        | READ/WRITE_EXTERNAL_STORAGE |
| `gps`         | Get current location coordinates          | ACCESS_FINE_LOCATION |
| `wifi`        | Scan networks, connect, get SSID/IP       | ACCESS_WIFI_STATE   |
| `nfc`         | Read/write NFC tags                       | NFC                 |
| `biometric`   | Fingerprint and face authentication       | USE_BIOMETRIC       |
| `notifications` | Show local push notifications           | POST_NOTIFICATIONS  |
| `accelerometer` | Read device motion and orientation      | none                |

---

## Build Time Comparison

| Operation           | Android Studio | Nano-Stack |
|---------------------|----------------|------------|
| First build         | 3–10 min       | < 5 sec    |
| Incremental build   | 30–90 sec      | < 5 sec    |
| APK size (simple app) | 2–5 MB      | ~3–4 MB    |
| RAM during build    | 2–4 GB         | < 100 MB   |

---

## Internet Requirements

| Task                           | Internet Required |
|--------------------------------|-------------------|
| Install Nano-Stack             | Yes (one-time)    |
| Create project                 | No                |
| Compile .nano → logic.json     | No                |
| Bundle APK                     | No                |
| Deploy to device               | No (USB only)     |

---

## CLI Reference

```
nano new <AppName>    Create a new project
nano check            Validate app.nano (no build)
nano build            Compile + bundle signed APK
nano run              Install + launch on device via adb
nano clean            Delete build/ folder
```

---

## License

MIT — see [LICENSE](LICENSE) for details.

## GitHub

https://github.com/yourname/nanostack
