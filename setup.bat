@echo off
echo =============================================
echo   Simple Call-Like Remote Desktop Tester
echo =============================================
echo.

echo [1] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python first.
    pause
    exit /b 1
)
echo ✓ Python is installed

echo.
echo [2] Checking audio devices...
echo.
python -c "
import pyaudio
try:
    p = pyaudio.PyAudio()
    print('=== INPUT DEVICES (for capturing audio) ===')
    has_input = False
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f'  {i}: {info[\"name\"]}')
            has_input = True
            if 'wasapi' in info['name'].lower() and 'loopback' in info['name'].lower():
                print('    ^ WASAPI LOOPBACK FOUND (BEST FOR SYSTEM AUDIO)')
            elif 'stereo mix' in info['name'].lower():
                print('    ^ STEREO MIX FOUND (GOOD FOR SYSTEM AUDIO)')
    
    print('\n=== OUTPUT DEVICES (for playing audio) ===')
    has_output = False        
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxOutputChannels'] > 0:
            print(f'  {i}: {info[\"name\"]}')
            has_output = True
            if 'speaker' in info['name'].lower() or 'headphone' in info['name'].lower():
                print('    ^ SPEAKERS/HEADPHONES FOUND')
    
    if not has_input:
        print('WARNING: No input devices found!')
    if not has_output:
        print('WARNING: No output devices found!')
        
    p.terminate()
    
except ImportError:
    print('ERROR: PyAudio not installed. Run: pip install PyAudio')
except Exception as e:
    print(f'ERROR: {e}')
"

echo.
echo [3] Getting system UUID...
echo.
for /f "skip=1 tokens=*" %%i in ('wmic csproduct get uuid ^| findstr /r /v "^$"') do (
    set UUID=%%i
    goto :uuid_found
)
:uuid_found
set UUID=%UUID: =%
echo Your system UUID is: %UUID%
echo.
echo IMPORTANT: Add this UUID to allowed.json on the server!

echo.
echo [4] Checking required files...
if exist "client.py" (
    echo ✓ client.py found
) else (
    echo ✗ client.py missing
)

if exist "server.py" (
    echo ✓ server.py found
) else (
    echo ✗ server.py missing
)

if exist "view.html" (
    echo ✓ view.html found
) else (
    echo ✗ view.html missing
)

if exist "allowed.json" (
    echo ✓ allowed.json found
    echo   Current allowed UUIDs:
    type allowed.json | findstr "allowed_uuids" -A 10
) else (
    echo ⚠ allowed.json missing - creating with your UUID...
    echo {
    echo   "allowed_uuids": [
    echo     "%UUID%"
    echo   ]
    echo } > allowed.json
    echo ✓ Created allowed.json with your UUID
)

echo.
echo [5] Testing audio setup...
echo.
echo Starting quick audio test...
python -c "
import pyaudio
import time
import numpy as np

try:
    p = pyaudio.PyAudio()
    
    # Test audio output
    print('Testing audio output (you should hear a beep)...')
    
    # Generate a simple beep
    sample_rate = 22050
    frequency = 440  # A note
    duration = 1  # seconds
    
    # Generate sine wave
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(frequency * 2 * np.pi * t) * 0.3  # 30% volume
    
    # Convert to 16-bit integers
    audio_data = (wave * 32767).astype(np.int16)
    
    # Play the beep
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        output=True
    )
    
    stream.write(audio_data.tobytes())
    stream.stop_stream()
    stream.close()
    
    print('✓ Audio output test completed')
    
    # Test audio input
    print('Testing audio input (speak for 3 seconds)...')
    
    input_stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        input=True,
        frames_per_buffer=1024
    )
    
    print('Recording... speak now!')
    frames = []
    for i in range(0, int(sample_rate / 1024 * 3)):  # 3 seconds
        data = input_stream.read(1024, exception_on_overflow=False)
        frames.append(data)
    
    print('Recording stopped.')
    
    input_stream.stop_stream()
    input_stream.close()
    
    # Check if we captured any audio
    audio_data = b''.join(frames)
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    max_volume = np.max(np.abs(audio_array))
    
    if max_volume > 1000:
        print(f'✓ Audio input working (max volume: {max_volume})')
    else:
        print(f'⚠ Audio input very quiet (max volume: {max_volume})')
        print('  Check microphone permissions and volume')
    
    p.terminate()
    
except Exception as e:
    print(f'Audio test failed: {e}')
"

echo.
echo =============================================
echo               TEST COMPLETE
echo =============================================
echo.
echo Next steps:
echo 1. Start the server: python server.py
echo 2. Start the client: python client.py wss://192.168.48.53:5444/ws
echo 3. Open browser: https://192.168.48.53:5444
echo 4. Test audio modes: Off → Listen → Talk → Both Ways
echo.
echo If audio doesn't work:
echo - Enable "Stereo Mix" in Windows sound settings
echo - Allow microphone permissions in browser
echo - Check firewall settings for port 5444
echo.
pause