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

## License

This project is provided as-is for educational and internal use purposes.