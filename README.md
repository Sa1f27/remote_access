# Remote Desktop Application

A Python-based remote desktop solution with WebCall audio routing capabilities, similar to AnyDesk.

## Architecture

- **Client**: Windows headless Python script for screen/audio sharing
- **Server**: Local GPU desktop with HTTPS/WSS server
- **Viewer**: Web-based interface for remote control
- **WebCall Integration**: Real-time audio routing for video calls

## Features

### Core Functionality
- Live screen sharing (20-30 FPS)
- System audio capture and streaming
- Remote mouse/keyboard control
- UUID-based client authorization
- Real-time connection monitoring

### WebCall Audio Routing
- **Client Only Mode**: Normal microphone audio to WebCall
- **Viewer Only Mode**: Only viewer's voice to WebCall (mutes client mic)
- **Merged Mode**: Combined client + viewer audio to WebCall
- Sub-150ms audio latency using WASAPI
- No virtual driver installation required

### Security & Monitoring
- HTTPS/WSS encrypted connections
- UUID whitelist validation
- Comprehensive logging in `L_sys_log.txt`
- Connection status and performance metrics

## Installation

### Prerequisites (Windows)
```cmd
# Install Chocolatey (if not installed)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install OpenSSL for certificates
choco install openssl -y

# Install Python (if not installed)
choco install python -y
```

### Automated Setup
```cmd
# Run the setup script
setup.bat
```

### Manual Installation
```cmd
# Install Python dependencies
pip install -r requirements.txt

# Install PortAudio for audio support
choco install portaudio -y

# Create SSL certificates
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

## Configuration

### 1. Get Client UUID
```cmd
wmic csproduct get uuid
```

### 2. Configure Server Authorization
Edit `allowed.json`:
```json
{
  "allowed_uuids": [
    "YOUR-CLIENT-UUID-HERE",
    "ANOTHER-UUID-IF-NEEDED"
  ]
}
```

### 3. Network Configuration
- Ensure port 5444 is open in firewall
- Configure router port forwarding if accessing externally
- Update server IP/domain in client connection string

## Usage

### Starting the Server
```cmd
# With SSL (recommended for production)
python server.py --cert server.crt --key server.key

# Without SSL (development only)
python server.py
```

### Starting the Client
```cmd
# Connect to HTTPS server
python client.py wss://your-server-ip:5444/ws

# Connect to HTTP server (development)
python client.py ws://your-server-ip:5444/ws
```

### Accessing the Viewer
1. Open browser to `https://your-server-ip:5444`
2. Enter client UUID on landing page
3. Use viewer interface to control remote desktop

## WebCall Audio Setup

### For Video Call Participants:
1. Start your WebCall (Zoom, Teams, GMeet)
2. Select your default microphone in the call
3. Start the remote desktop client
4. Viewer can now control audio routing:
   - **Client Only**: Normal operation
   - **Viewer Only**: Your voice replaces client's voice
   - **Merged**: Both voices combined

### Audio Routing Modes:
- **Client Only Mode** (Default): Client's microphone → WebCall
- **Viewer Only Mode**: Viewer's voice → Client's mic input → WebCall
- **Merged Mode**: (Client mic + Viewer voice) → WebCall

## Performance Optimization

### Client-Side
- Close unnecessary applications
- Use wired internet connection
- Ensure stable power supply
- Monitor CPU/GPU usage

### Server-Side
- Use dedicated GPU server
- Optimize network bandwidth
- Monitor concurrent connections
- Regular log cleanup

### Network
- Target <150ms latency for audio
- Minimum 10 Mbps upload for quality video
- Use ethernet over WiFi when possible

## Troubleshooting

### Audio Issues
```cmd
# Check audio devices
python -c "import pyaudio; p=pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"

# Test microphone access
# Ensure microphone permissions are enabled for Python
```

### Connection Issues
```cmd
# Test WebSocket connection
python -c "import asyncio, websockets; asyncio.run(websockets.connect('wss://your-server:5444/ws'))"

# Check SSL certificate
openssl s_client -connect your-server:5444 -servername your-server
```

### UUID Authorization
```cmd
# Verify client UUID
wmic csproduct get uuid

# Check server logs
type L_sys_log.txt | findstr UUID
```

## File Structure
```
remote-desktop/
├── client.py              # Client application
├── server.py              # Server application  
├── land.html              # Landing page
├── view.html              # Viewer interface
├── requirements.txt       # Python dependencies
├── allowed.json           # Authorized UUIDs
├── setup.bat              # Setup script
├── server.crt             # SSL certificate
├── server.key             # SSL private key
├── L_sys_log.txt          # System logs
└── README.md              # This file
```

## Security Considerations

### Production Deployment
- Use proper CA-signed SSL certificates
- Implement IP whitelisting
- Regular UUID rotation
- VPN access for external connections
- Monitor logs for unauthorized access attempts

### Data Protection
- All connections encrypted with TLS
- No data persistence on server
- UUID-based access control
- Automatic connection cleanup

## Performance Metrics

### Target Performance
- **Screen Sharing**: 20-30 FPS at 1080p
- **Audio Latency**: <150ms end-to-end
- **Control Responsiveness**: <50ms mouse/keyboard
- **Connection Stability**: 99%+ uptime

### Monitoring
- Real-time latency display
- FPS counter
- Connection uptime
- Network performance stats

## Common Issues & Solutions

### "PyAudio not found"
```cmd
# Install PortAudio first
choco install portaudio -y
pip install pyaudio

# Alternative: Use conda
conda install pyaudio
```

### "SSL Certificate Error"
```cmd
# Regenerate certificates
del server.crt server.key
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes
```

### "WebSocket Connection Failed"
- Check firewall settings
- Verify server is running
- Confirm correct URL/port
- Test with HTTP first

### "UUID Not Authorized"
- Add UUID to `allowed.json`
- Restart server after changes
- Verify UUID format is correct

## Support

For technical issues:
1. Check logs in `L_sys_log.txt`
2. Verify network connectivity
3. Test with simplified configuration
4. Review system requirements


# Troubleshoot

# Simple Call-Like Remote Desktop - Setup Guide

## What Changed (No More Alien Voice!)

✅ **Fixed audio quality**: Removed complex processing that was causing distortion  
✅ **Two-way audio**: Client microphone now properly reaches viewer  
✅ **Call-like controls**: Simple buttons for different audio modes  
✅ **Cleaner code**: Much simpler, more reliable audio handling  

## Audio Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **🔇 Audio Off** | No audio transmission | Silent monitoring |
| **🔊 Listen Only** | Hear client's computer audio + mic | Listen to what's happening |
| **🎤 Talk Only** | Your microphone goes to client | Give instructions |
| **📞 Both Ways** | Full two-way communication | Phone call experience |

## Quick Setup

### 1. Replace Files
Replace your existing files with the new versions:
- `client.py` → Simple Call-Like Audio Client
- `view.html` → Simple Call-Like Viewer  
- `server.py` → Updated Server for Call-Like Audio

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Check Your UUID
```bash
# Get your client machine's UUID
wmic csproduct get uuid
```

### 4. Update allowed.json
Add your UUID to `allowed.json`:
```json
{
  "allowed_uuids": [
    "YOUR-ACTUAL-UUID-HERE"
  ]
}
```

### 5. Start Server
```bash
python server.py --cert server.crt --key server.key
```

### 6. Start Client
```bash
python client.py wss://192.168.48.53:5444/ws
```

### 7. Open Viewer
Go to: `https://192.168.48.53:5444`

## Testing Audio

### Step 1: Test "Listen Only" Mode
1. Click **🔊 Listen Only** in viewer
2. Play music on client computer
3. You should hear the music clearly (no alien voice!)

### Step 2: Test "Talk Only" Mode  
1. Click **🎤 Talk Only** in viewer
2. Allow microphone permission when prompted
3. Speak into your microphone
4. You should hear your voice from client computer speakers

### Step 3: Test "Both Ways" Mode
1. Click **📞 Both Ways** in viewer
2. Now you can hear client AND talk to client
3. Like a phone call!

## Troubleshooting

### "No system audio from client"
```bash
# Check if Stereo Mix is enabled on client computer
1. Right-click sound icon → Recording devices
2. Right-click empty space → Show disabled devices  
3. Enable "Stereo Mix" if available
4. Set as default recording device
```

### "Microphone permission denied"
1. Click the 🔒 lock icon in browser address bar
2. Allow microphone access
3. Refresh the page
4. Try audio mode again

### "Audio is choppy"
- Lower the screen quality in client code
- Check network connection
- Close other applications using audio

### "Can't hear viewer audio on client"
The client will automatically detect speakers. If not working:
```python
# In client.py, add debug to see audio devices:
audio_manager.list_audio_devices()
```

## Debug Commands

### Check Client Audio Devices
```bash
python -c "
import pyaudio
p = pyaudio.PyAudio()
print('=== INPUT DEVICES ===')
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'{i}: {info[\"name\"]}')

print('\n=== OUTPUT DEVICES ===')        
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxOutputChannels'] > 0:
        print(f'{i}: {info[\"name\"]}')
"
```

### Test Network Connection
```bash
# Test if client can reach server
telnet 192.168.48.53 5444
```

### Check Server Logs
```bash
# Watch server logs in real-time
tail -f L_sys_log.txt
```

## Browser Requirements

### Microphone Support
- ✅ Chrome/Edge: Full support
- ✅ Firefox: Full support  
- ⚠️ Safari: Limited support
- ❌ Internet Explorer: Not supported

### Required Permissions
- **Microphone**: For talk modes
- **Autoplay**: For audio playback
- **Fullscreen**: For immersive mode

## Performance Tips

### If Audio is Lagging
1. Reduce screen frame rate in client:
   ```python
   frame_time = 1.0 / 10  # 10 FPS instead of 15
   ```

2. Lower audio quality:
   ```python
   self.rate = 16000  # Lower sample rate
   self.chunk = 4096  # Larger chunks
   ```

### If Screen is Slow
1. Reduce image quality:
   ```python
   self.quality = 50  # Lower JPEG quality
   ```

2. Limit screen size:
   ```python
   img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
   ```

## Common Issues Fixed

❌ **Old Issue**: "Alien voice distortion"  
✅ **Fixed**: Simple audio conversion without complex processing

❌ **Old Issue**: "No two-way audio"  
✅ **Fixed**: Proper message routing for microphone audio

❌ **Old Issue**: "Complex audio controls"  
✅ **Fixed**: Simple call-like buttons (Off/Listen/Talk/Both)

❌ **Old Issue**: "Audio output to wrong device"  
✅ **Fixed**: Auto-detect speakers instead of microphone

## File Locations

Make sure these files are in your project folder:
```
project/
├── client.py          (Simple Call-Like Audio Client)
├── server.py          (Updated Server)  
├── view.html          (Simple Call-Like Viewer)
├── land.html          (Landing page - keep existing)
├── allowed.json       (Add your UUID here)
├── server.crt         (SSL certificate)
├── server.key         (SSL private key)
├── requirements.txt   (Python dependencies)
└── L_sys_log.txt      (Server logs - auto-created)
```

## Success Indicators

When everything is working correctly, you should see:

**Client Console:**
```
✓ Started system audio capture: WASAPI loopback
✓ Started microphone capture
✓ Started speaker output: Realtek Audio
✓ Audio system started successfully
Connected to server with UUID: YOUR-UUID
```

**Viewer Interface:**
```
Status: Connected
Audio: Full Call (when in Both Ways mode)
```

**Server Logs:**
```
CLIENT CONNECT - UUID: YOUR-UUID, IP: 192.168.x.x
VIEWER CONNECT - UUID: YOUR-UUID, IP: 192.168.x.x  
AUDIO MODE CHANGE - UUID: YOUR-UUID, Mode: both
```

The audio should now be clear and work in both directions like a normal phone call! 🎉