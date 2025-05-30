#!/usr/bin/env python3
"""
Audio Debug Script - Run this on the CLIENT machine to fix audio capture
"""

import pyaudio
import time
import subprocess
import sys

def check_windows_audio_settings():
    """Check Windows audio settings"""
    print("=== WINDOWS AUDIO SETTINGS CHECK ===")
    
    try:
        # Check if Stereo Mix is available
        result = subprocess.run([
            'powershell', '-Command',
            "Get-WmiObject -Class Win32_SoundDevice | Select-Object Name, Status"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("Audio devices found:")
            print(result.stdout)
        else:
            print("Could not query audio devices via PowerShell")
    except:
        print("PowerShell query failed, checking manually...")

def list_detailed_audio_devices():
    """List all audio devices with detailed info"""
    print("\n=== DETAILED AUDIO DEVICE LIST ===")
    
    try:
        p = pyaudio.PyAudio()
        
        print("INPUT DEVICES (what we can record from):")
        print("-" * 50)
        
        input_devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                input_devices.append((i, info))
                name = info['name']
                channels = info['maxInputChannels']
                rate = int(info['defaultSampleRate'])
                
                print(f"  [{i}] {name}")
                print(f"      Channels: {channels}, Sample Rate: {rate} Hz")
                
                # Check for special devices
                name_lower = name.lower()
                if 'wasapi' in name_lower and 'loopback' in name_lower:
                    print("      ★ WASAPI LOOPBACK - PERFECT for system audio!")
                elif 'stereo mix' in name_lower:
                    print("      ★ STEREO MIX - GOOD for system audio!")
                elif 'what u hear' in name_lower:
                    print("      ★ WHAT U HEAR - GOOD for system audio!")
                elif 'microphone' in name_lower:
                    print("      • Regular microphone")
                elif 'line in' in name_lower:
                    print("      • Line input")
                else:
                    print("      ? Unknown device type")
                print()
        
        print(f"\nTotal input devices found: {len(input_devices)}")
        
        if not input_devices:
            print("❌ NO INPUT DEVICES FOUND!")
            print("This is why you can't hear client audio.")
            
        p.terminate()
        return input_devices
        
    except Exception as e:
        print(f"Error listing devices: {e}")
        return []

def test_device_recording(device_index, device_name):
    """Test recording from a specific device"""
    print(f"\n=== TESTING DEVICE [{device_index}]: {device_name} ===")
    
    try:
        p = pyaudio.PyAudio()
        
        # Try to open the device
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=22050,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=2048
        )
        
        print("✓ Device opened successfully")
        print("Recording 3 seconds of audio... (play some music/sounds now)")
        
        # Record for 3 seconds
        frames = []
        for i in range(0, int(22050 / 2048 * 3)):
            try:
                data = stream.read(2048, exception_on_overflow=False)
                frames.append(data)
                if i % 10 == 0:
                    print(".", end="", flush=True)
            except Exception as e:
                print(f"\nError reading from device: {e}")
                break
        
        print("\n✓ Recording completed")
        
        # Analyze the audio
        import numpy as np
        audio_data = b''.join(frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        max_volume = np.max(np.abs(audio_array))
        avg_volume = np.mean(np.abs(audio_array))
        
        print(f"Audio Analysis:")
        print(f"  Max Volume: {max_volume}")
        print(f"  Avg Volume: {avg_volume}")
        
        if max_volume > 5000:
            print("  ✓ STRONG AUDIO SIGNAL - This device is working!")
            return True
        elif max_volume > 1000:
            print("  ⚠ WEAK AUDIO SIGNAL - Device works but might be quiet")
            return True
        else:
            print("  ❌ NO AUDIO SIGNAL - Device not capturing audio")
            return False
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
    except Exception as e:
        print(f"❌ Failed to test device: {e}")
        return False

def enable_stereo_mix_instructions():
    """Show instructions to enable Stereo Mix"""
    print("\n" + "="*60)
    print("HOW TO ENABLE STEREO MIX (to hear client audio)")
    print("="*60)
    print("""
1. Right-click the SPEAKER ICON in system tray
2. Click "Open Sound settings"
3. Scroll down and click "Sound Control Panel"
4. Go to the "RECORDING" tab
5. Right-click in empty space → "Show Disabled Devices"
6. Look for "Stereo Mix" and right-click it
7. Click "Enable"
8. Right-click "Stereo Mix" again → "Set as Default Device"
9. Click "OK" to close

Alternative method:
1. Right-click speaker icon → "Sounds"
2. Recording tab → Right-click empty space
3. "Show Disabled Devices" and "Show Disconnected Devices"
4. Enable "Stereo Mix"

If Stereo Mix is not available:
- Your audio driver might not support it
- Try updating your audio drivers (Realtek, etc.)
- Or install VB-Cable (Virtual Audio Cable) software
""")

def suggest_solutions(working_devices):
    """Suggest solutions based on test results"""
    print("\n" + "="*60)
    print("SOLUTIONS")
    print("="*60)
    
    if not working_devices:
        print("❌ NO WORKING AUDIO CAPTURE DEVICES FOUND")
        print("\nTo fix this:")
        print("1. Enable Stereo Mix (see instructions above)")
        print("2. Update your audio drivers")
        print("3. Install VB-Cable virtual audio device")
        print("4. Check Windows privacy settings for microphone access")
        
    else:
        print("✓ WORKING DEVICES FOUND:")
        for device_id, device_name in working_devices:
            print(f"  [{device_id}] {device_name}")
        
        print(f"\nTo fix the client audio:")
        print("1. Make sure client.py uses one of the working devices above")
        print("2. The client should automatically detect these devices")
        print("3. If still not working, manually specify device in client code")

def main():
    print("CLIENT AUDIO DIAGNOSTIC TOOL")
    print("=" * 40)
    print("This will help fix the 'cant hear client audio' problem")
    print()
    
    # Check Windows audio settings
    check_windows_audio_settings()
    
    # List all devices
    input_devices = list_detailed_audio_devices()
    
    if not input_devices:
        enable_stereo_mix_instructions()
        return
    
    # Test each potential system audio device
    print("\n" + "="*60)
    print("TESTING DEVICES FOR SYSTEM AUDIO CAPTURE")
    print("="*60)
    print("Play some music or sounds during these tests...")
    
    working_devices = []
    
    for device_id, device_info in input_devices:
        name = device_info['name']
        name_lower = name.lower()
        
        # Test devices that might capture system audio
        if ('wasapi' in name_lower and 'loopback' in name_lower) or \
           'stereo mix' in name_lower or \
           'what u hear' in name_lower:
            
            print(f"\nTesting {name}...")
            input("Press ENTER to start test (make sure music is playing)...")
            
            if test_device_recording(device_id, name):
                working_devices.append((device_id, name))
    
    # Show solutions
    suggest_solutions(working_devices)
    
    if working_devices:
        print(f"\n✓ Found {len(working_devices)} working audio capture device(s)")
        print("The client should now be able to capture system audio!")
    else:
        print("\n❌ No working system audio capture found")
        print("You need to enable Stereo Mix or install virtual audio software")
    
    print("\nPress ENTER to exit...")
    input()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
        input("Press ENTER to exit...")