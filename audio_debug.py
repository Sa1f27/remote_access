#!/usr/bin/env python3
"""
Microphone Permission Test - Run this on CLIENT machine
Tests microphone access and Windows privacy settings
"""

import pyaudio
import numpy as np
import time
import subprocess

def check_windows_microphone_privacy():
    """Check Windows microphone privacy settings"""
    print("🔐 Checking Windows microphone privacy settings...")
    
    try:
        # Check app microphone access
        result = subprocess.run([
            'powershell', '-Command',
            """
            $mic = Get-WinUserPrivacySetting -SettingType Microphone
            Write-Output "Microphone Access: $($mic.State)"
            
            $apps = Get-AppxPackage | Get-WinUserPrivacySetting -SettingType Microphone
            Write-Output "Desktop Apps Microphone Access:"
            Get-WinUserPrivacySetting -SettingType Microphone | Where-Object {$_.AppDisplayName -eq $null} | ForEach-Object {
                Write-Output "  Desktop Apps: $($_.State)"
            }
            """
        ], capture_output=True, text=True, timeout=10)
        
        print("Windows Privacy Settings:")
        print(result.stdout)
        
        if "Denied" in result.stdout:
            print("❌ MICROPHONE ACCESS DENIED IN WINDOWS PRIVACY SETTINGS")
            print("🔧 TO FIX:")
            print("   1. Press Win + I")
            print("   2. Go to Privacy & Security → Microphone")
            print("   3. Turn ON 'Let apps access your microphone'")
            print("   4. Turn ON 'Let desktop apps access your microphone'")
            return False
        elif "Allowed" in result.stdout:
            print("✅ Windows microphone privacy settings are correct")
            return True
        else:
            print("❓ Could not determine privacy settings")
            return True
            
    except Exception as e:
        print(f"⚠ Could not check privacy settings: {e}")
        return True

def test_microphone_access():
    """Test direct microphone access"""
    print("\n🎤 Testing microphone access...")
    
    try:
        p = pyaudio.PyAudio()
        
        # List microphone devices
        print("\nAvailable microphone devices:")
        mic_devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name = info['name']
                print(f"  [{i}] {name}")
                if 'microphone' in name.lower():
                    mic_devices.append((i, name))
        
        if not mic_devices:
            print("❌ No microphone devices found!")
            return False
        
        # Test each microphone
        for device_id, device_name in mic_devices:
            print(f"\n🎤 Testing microphone [{device_id}]: {device_name}")
            
            try:
                # Try to open microphone
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=device_id,
                    frames_per_buffer=1024
                )
                
                print("✓ Microphone opened successfully")
                print("🎤 Testing audio capture (speak now for 3 seconds)...")
                
                max_level = 0
                for i in range(int(16000 / 1024 * 3)):  # 3 seconds
                    try:
                        data = stream.read(1024, exception_on_overflow=False)
                        audio_array = np.frombuffer(data, dtype=np.int16)
                        level = np.max(np.abs(audio_array))
                        max_level = max(max_level, level)
                        
                        if i % 10 == 0:  # Print every ~0.6 seconds
                            print(f"  Audio level: {level:5d} {'🎤' if level > 500 else '🔇'}")
                            
                    except Exception as e:
                        print(f"  Read error: {e}")
                        break
                
                stream.close()
                
                if max_level > 500:
                    print(f"✅ MICROPHONE WORKING! Max level: {max_level}")
                    print(f"✅ Device [{device_id}] can capture audio properly")
                    p.terminate()
                    return True
                else:
                    print(f"⚠ Microphone very quiet. Max level: {max_level}")
                    print("   Check microphone volume or try speaking louder")
                
            except Exception as e:
                print(f"❌ Failed to access microphone: {e}")
                
                if "Access is denied" in str(e) or "Unanticipated host error" in str(e):
                    print("❌ MICROPHONE ACCESS DENIED!")
                    print("   This is likely a Windows privacy setting issue")
                    return False
        
        p.terminate()
        return False
        
    except Exception as e:
        print(f"❌ PyAudio error: {e}")
        return False

def fix_microphone_issues():
    """Suggest fixes for microphone issues"""
    print("\n🔧 MICROPHONE TROUBLESHOOTING GUIDE")
    print("=" * 50)
    
    print("\n1. CHECK WINDOWS PRIVACY SETTINGS:")
    print("   • Press Win + I → Privacy & Security → Microphone")
    print("   • Turn ON 'Let apps access your microphone'")
    print("   • Turn ON 'Let desktop apps access your microphone'")
    
    print("\n2. CHECK MICROPHONE VOLUME:")
    print("   • Right-click speaker icon → Open Sound settings")
    print("   • Go to Input → Choose input device")
    print("   • Test microphone and adjust volume")
    
    print("\n3. CHECK IF MICROPHONE IS IN USE:")
    print("   • Close Zoom, Teams, Discord, or other apps using microphone")
    print("   • Check Task Manager for audio applications")
    
    print("\n4. TRY RUNNING AS ADMINISTRATOR:")
    print("   • Right-click Command Prompt → Run as administrator")
    print("   • Navigate to your project folder")
    print("   • Run: python client.py wss://192.168.48.53:5444/ws")
    
    print("\n5. UPDATE AUDIO DRIVERS:")
    print("   • Device Manager → Audio inputs and outputs")
    print("   • Right-click microphone → Update driver")

def main():
    print("🎤 MICROPHONE PERMISSION & ACCESS TEST")
    print("=" * 50)
    print("This will test if Python can access your microphone")
    print("Run this on the CLIENT machine (where client.py runs)")
    
    # Check Windows privacy settings
    privacy_ok = check_windows_microphone_privacy()
    
    # Test microphone access
    mic_ok = test_microphone_access()
    
    print("\n" + "=" * 50)
    print("📋 TEST RESULTS:")
    print(f"Windows Privacy Settings: {'✅ OK' if privacy_ok else '❌ DENIED'}")
    print(f"Microphone Access: {'✅ WORKING' if mic_ok else '❌ FAILED'}")
    
    if privacy_ok and mic_ok:
        print("\n🎉 MICROPHONE IS WORKING!")
        print("✅ Your audio client should be able to capture microphone audio")
        print("✅ Two-way communication should work in call modes: Talk/Both")
    else:
        print("\n❌ MICROPHONE ACCESS PROBLEMS DETECTED")
        fix_microphone_issues()
    
    print("\nPress ENTER to exit...")
    input()

if __name__ == "__main__":
    main()