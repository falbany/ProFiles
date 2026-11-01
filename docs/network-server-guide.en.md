# Guide: ProFiles Network Server

**Version**: 1.0  
**Date**: 2026-10-15  
**Feature**: Local network sharing — access from other PCs

---

## 📖 Introduction

This guide explains how to make ProFiles accessible from other PCs on your local network, so that colleagues or other machines can access the files hosted on your PC.

---

## 🎯 Prerequisites

### System Requirements

- **Host PC**: Windows with ProFiles installed
- **Client PCs**: Any PC with a modern web browser
- **Network**: All PCs must be on the same local network (same subnet)

### Checks

1. **Same network**: Make sure all PCs are on the same network (e.g. 192.168.1.x)
2. **Firewall**: Windows Firewall must be configured to allow port 8088
3. **ProFiles installed**: The host PC must have a working ProFiles installation

---

## 🚀 Configuring the Host PC

### Step 1: Allow the port in the firewall

Open PowerShell **as administrator** and run:

```powershell
New-NetFirewallRule -DisplayName "ProFiles Server" -Direction Inbound -Protocol TCP -LocalPort 8088 -Action Allow
```

**Alternative through the graphical interface**:

1. Open "Windows Defender Firewall with Advanced Security"
2. Click "Inbound Rules"
3. "New Rule..." → "Port" → "TCP" → "8088"
4. "Allow the connection"
5. Name it "ProFiles Server"

### Step 2: Start the server

In a terminal, run:

```powershell
ProFiles --server-only
```

**Expected output**:

```
ProFiles server running at:
  Local:  http://127.0.0.1:8088
  Network: http://192.168.1.100:8088
  Access from other PCs on your network (press Ctrl+C to stop)
```

**Important note**: Note the **Network** address (e.g. `192.168.1.100:8088`) — this is the URL the other PCs will use.

### Step 3: Verify the server is running

Open your browser on the host PC and go to:

```
http://127.0.0.1:8088
```

You should see the ProFiles interface.

---

## 💻 Accessing from Client PCs

### Step 1: Open the browser

On a client PC (on the same network), open any modern browser:

- Chrome, Edge, Firefox, Safari

### Step 2: Go to the server URL

In the address bar, enter the URL displayed on the host PC:

```
http://192.168.1.100:8088
```

**Replace** `192.168.1.100` with the actual IP shown on the host PC.

### Step 3: Use the interface

The ProFiles interface appears exactly as it does on the host PC:

- ✅ **File scanning**: Click "Scan" to list the files
- ✅ **Filtering**: Filter by extension (.txt, .py, etc.)
- ✅ **Launching**: Click a file to launch it **on the host PC**
- ✅ **Configuration**: Load custom configurations

**Important**: Files are launched on the **host PC**, not on the client PC.

---

## 🔧 Advanced Configuration

### Changing the default port

If port 8088 is already taken, you can use a different one. The default port is not defined in a single place: it appears as the default value of several constants in the source code.

Edit the following defaults:

```python
# src/profiles/app.py — module-level constant used by --server-only mode
_DEFAULT_PORT = 9090

# src/profiles/desktop/lifecycle.py — fallback probe and background server
def find_available_port(start_port: int = 9090, max_attempts: int = 50) -> int:  # line 35
    ...

class BackgroundServer:
    def __init__(self, config: AppConfig, host: str = "0.0.0.0", port: int = 9090) -> None:  # line 63
        # line 66 also calls find_available_port(9090) when port == 0
        ...

# src/profiles/desktop/launcher.py — desktop entry point
def launch_desktop_window(
    config: AppConfig,
    port: int = 9090,  # line 65
    ...
```

Locations of the default values (as of the current source tree):

| File | Line | Constant / default |
|---|---|---|
| `src/profiles/app.py` | 36 | `_DEFAULT_PORT = 8088` |
| `src/profiles/desktop/lifecycle.py` | 35 | `find_available_port(start_port=8088)` |
| `src/profiles/desktop/lifecycle.py` | 63 | `BackgroundServer.__init__(..., port=8088)` |
| `src/profiles/desktop/launcher.py` | 65 | `launch_desktop_window(..., port=8088)` |

Note that a busy port is never fatal: the server probes the next free port automatically (up to 50 attempts from the starting port, then falls back to an OS-assigned ephemeral port).

The CLI currently does **not** expose a `--port` option; changing the port requires editing the constants above.

### Static IP for the host PC

To prevent the IP address from changing on every reboot:

1. **Via the router**: Configure a DHCP reservation for the host PC
2. **Via Windows**: Configure a manual static IP

**Example static configuration**:

```
IP Address: 192.168.1.100
Subnet Mask: 255.255.255.0
Gateway: 192.168.1.1
DNS: 8.8.8.8
```

### Stopping the server

Press **Ctrl+C** in the terminal where the server is running.

---

## 🛡️ Security

### Best Practices

✅ **Do**:
- Use it on a trusted network (office, home)
- Configure Windows Firewall
- Limit access to authorized users
- Monitor the server logs

❌ **Avoid**:
- Do **NOT** set up port forwarding on the router
- Do **NOT** expose it to the Internet (public Wi-Fi, guest network)
- Do **NOT** share the URL outside the local network
- Do **NOT** use it for sensitive files without authentication

### Current Security Level

⚠️ **Warning**: This setup has **no authentication**. It is designed for trusted local networks.

**For stronger security**:
- Use a VPN to access the network
- Set up a reverse proxy with authentication (Nginx, Apache)
- Consider Option B (authentication) as a future evolution

---

## 🐛 Troubleshooting

### Problem: "Unable to connect" on the client PC

**Cause**: Firewall blocking port 8088

**Solution**:
```powershell
# Check the firewall rule on the host PC
Get-NetFirewallRule -DisplayName "ProFiles Server"

# If it is missing, recreate it
New-NetFirewallRule -DisplayName "ProFiles Server" -Direction Inbound -Protocol TCP -LocalPort 8088 -Action Allow
```

### Problem: "Connection refused"

**Cause**: Server not started or port already in use

**Solution**:
```powershell
# Check whether the server is running
netstat -ano | findstr :8088

# If the port is taken, switch ports or stop the other process
taskkill /PID <PID> /F
```

### Problem: The IP address changes on every reboot

**Cause**: DHCP assigns a different IP address

**Solution**:
- Configure a DHCP reservation on the router
- Or configure a static IP on the host PC

### Problem: "Network unreachable"

**Cause**: Client PCs on a different subnet

**Solution**:
- Make sure all PCs are on the same subnet (e.g. 192.168.1.x)
- Check the subnet mask (usually 255.255.255.0)

### Problem: Files do not launch

**Cause**: Incorrect file path or missing file

**Solution**:
- Make sure the files exist on the host PC
- Check the file access permissions
- Check the server logs for errors

---

## 📊 Performance

### Known Limitations

| Metric | Recommended Value |
|----------|-------------------|
| Number of files | < 10,000 |
| Directory depth | < 10 levels |
| Network latency | < 50 ms |
| Bandwidth | > 100 Mbps |

### Optimizations

- **Initial scan**: May take a few seconds for large directories
- **Filters**: Use the extension filters to shorten the list
- **Active directory**: Select a specific directory rather than the root

---

## 📝 Usage Example

### Scenario: Shared office

**Context**: 3 PCs in an office, files centralized on the main PC

**Setup**:
- **Host PC**: 192.168.1.100 (shared files)
- **Client PC 1**: 192.168.1.101
- **Client PC 2**: 192.168.1.102

**Workflow**:
1. Host PC: `ProFiles --server-only`
2. Client PC 1: Browser → `http://192.168.1.100:8088`
3. Client PC 2: Browser → `http://192.168.1.100:8088`
4. Everyone can scan and launch the files on the host PC

---

## 🔮 Future Evolutions

### Authentication (Option B)

Add an access token or basic authentication to secure access.

### Auto-discovery (Option C)

Use mDNS/Bonjour so that client PCs can discover the server automatically.

### HTTPS (Option D)

Encrypt communications with an SSL certificate.

---

## 📚 Resources

- [Spec technique](../specs/2026-10-15-network-server-design.md)
- [README principal](../../README.md)
- [Guide d'installation](../installation-guide.en.md)

---

**Last updated**: 2026-10-15  
**Author**: ProFiles Team  
**Version**: 1.0
