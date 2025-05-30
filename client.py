#!/usr/bin/env python3
"""
Audio-Only Remote Call Client
- Captures system audio (music, Zoom meetings, etc.)
- Captures microphone (client speaking)
- Plays viewer's voice through speakers
- No screen/keyboard/mouse access
"""

import asyncio
import json
import ssl
import subprocess
import sys
import time
import threading
import queue
from base64 import b64encode, b64decode
import websockets
import pyaudio
import numpy as np

class AudioOnlyManager:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.system_audio_stream = None   # For capturing system audio (Zoom, music, etc.)
        self.mic_stream = None           # For capturing client microphone
        self.speaker_stream = None       # For playing viewer's voice
        
        self.system_audio_queue = queue.Queue()
        self.mic_audio_queue = queue.Queue()
        self.viewer_audio_queue = queue.Queue()
        self.running = False
        
        # Audio settings - optimized for voice calls
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000  # Lower rate for voice calls (better for network)
        self.chunk = 1024
        
        # Call modes: "off", "listen", "talk", "both"
        self.call_mode = "off"
        
    def list_audio_devices(self):
        """Debug function to list all audio devices"""
        print("\n=== AUDIO DEVICES ===")
        print("INPUT DEVICES (Microphones, System Audio):")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name = info['name']
                print(f"  [{i}] {name}")
                if 'stereo mix' in name.lower() or 'wasapi' in name.lower() and 'loopback' in name.lower():
                    print(f"      ★ SYSTEM AUDIO DEVICE")
                elif 'microphone' in name.lower():
                    print(f"      🎤 MICROPHONE DEVICE")
        
        print("\nOUTPUT DEVICES (Speakers, Headphones):")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                name = info['name']
                print(f"  [{i}] {name}")
                if 'speaker' in name.lower() or 'headphone' in name.lower():
                    print(f"      🔊 SPEAKER DEVICE")
        print()
    
    def find_system_audio_device(self):
        """Find the best device for capturing system audio"""
        devices_to_try = []
        
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name_lower = info['name'].lower()
                
                # Priority order for system audio capture
                if 'wasapi' in name_lower and 'loopback' in name_lower:
                    devices_to_try.insert(0, (i, info['name'], 'WASAPI'))  # Highest priority
                elif 'stereo mix' in name_lower:
                    devices_to_try.append((i, info['name'], 'Stereo Mix'))
                elif 'what u hear' in name_lower:
                    devices_to_try.append((i, info['name'], 'What U Hear'))
        
        # Test each device to see which one works
        for device_id, device_name, device_type in devices_to_try:
            try:
                test_stream = self.p.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=device_id,
                    frames_per_buffer=self.chunk
                )
                test_stream.close()
                print(f"✓ Found working system audio device: [{device_id}] {device_name}")
                return device_id
            except Exception as e:
                print(f"✗ Device [{device_id}] failed: {e}")
        
        print("❌ No working system audio device found!")
        print("Please enable Stereo Mix or install virtual audio cable")
        return None
    
    def find_microphone_device(self):
        """Find the best microphone device"""
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name_lower = info['name'].lower()
                if 'microphone' in name_lower and 'array' not in name_lower:
                    try:
                        test_stream = self.p.open(
                            format=self.format,
                            channels=self.channels,
                            rate=self.rate,
                            input=True,
                            input_device_index=i,
                            frames_per_buffer=self.chunk
                        )
                        test_stream.close()
                        print(f"✓ Found microphone: [{i}] {info['name']}")
                        return i
                    except:
                        continue
        
        print("⚠ Using default microphone")
        return None  # Use default
    
    def find_speaker_device(self):
        """Find the best speaker device"""
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                name_lower = info['name'].lower()
                if ('speaker' in name_lower or 'headphone' in name_lower or 
                    'realtek' in name_lower) and 'microphone' not in name_lower:
                    try:
                        test_stream = self.p.open(
                            format=self.format,
                            channels=self.channels,
                            rate=self.rate,
                            output=True,
                            output_device_index=i,
                            frames_per_buffer=self.chunk
                        )
                        test_stream.close()
                        print(f"✓ Found speakers: [{i}] {info['name']}")
                        return i
                    except:
                        continue
        
        print("⚠ Using default speakers")
        return None  # Use default
    
    def start_system_audio_capture(self):
        """Start capturing system audio (Zoom, music, etc.)"""
        device_id = self.find_system_audio_device()
        if device_id is None:
            return False
        
        try:
            self.system_audio_stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.chunk
            )
            print("✓ System audio capture started")
            return True
        except Exception as e:
            print(f"✗ System audio capture failed: {e}")
            return False
    
    def start_microphone_capture(self):
        """Start capturing microphone"""
        print("🎤 Requesting microphone access...")
        
        device_id = self.find_microphone_device()
        
        try:
            # Test microphone access first
            print("🔐 Testing microphone permissions...")
            test_stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.chunk
            )
            
            # Test recording for 1 second to verify it works
            print("🎤 Testing microphone recording (speak now)...")
            for i in range(int(self.rate / self.chunk)):
                try:
                    data = test_stream.read(self.chunk, exception_on_overflow=False)
                    audio_level = np.max(np.abs(np.frombuffer(data, dtype=np.int16)))
                    if audio_level > 500:
                        print(f"✓ Microphone working! Level: {audio_level}")
                        break
                except Exception as e:
                    print(f"⚠ Microphone test issue: {e}")
            
            test_stream.close()
            
            # Now open the actual microphone stream
            self.mic_stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.chunk
            )
            print("✓ Microphone capture started successfully")
            print("🎤 Your voice will be transmitted when call mode allows it")
            return True
            
        except Exception as e:
            print(f"❌ Microphone capture failed: {e}")
            print("❌ Possible causes:")
            print("   • Microphone is being used by another application")
            print("   • Windows privacy settings block microphone access")
            print("   • Microphone driver issues")
            print("   • Run as Administrator might be needed")
            
            # Check Windows privacy settings
            try:
                result = subprocess.run([
                    'powershell', '-Command',
                    "Get-WinUserPrivacySetting -SettingType Microphone"
                ], capture_output=True, text=True, timeout=5)
                
                if "Denied" in result.stdout:
                    print("❌ Windows Privacy: Microphone access is DENIED")
                    print("🔧 Fix: Settings → Privacy → Microphone → Allow apps to access microphone")
                elif "Allowed" in result.stdout:
                    print("✅ Windows Privacy: Microphone access is allowed")
                else:
                    print("❓ Could not check Windows microphone privacy settings")
                    
            except Exception:
                print("❓ Could not check Windows privacy settings")
            
            return False
    
    def start_speaker_output(self):
        """Start speaker output for viewer's voice"""
        device_id = self.find_speaker_device()
        
        try:
            self.speaker_stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                output=True,
                output_device_index=device_id,
                frames_per_buffer=self.chunk
            )
            print("✓ Speaker output started")
            return True
        except Exception as e:
            print(f"✗ Speaker output failed: {e}")
            return False
    
    def audio_capture_thread(self):
        """Background thread to capture audio"""
        print("🎵 Audio capture thread started")
        
        while self.running:
            try:
                # Capture system audio (if in listen mode)
                if (self.system_audio_stream and 
                    self.call_mode in ["listen", "both"]):
                    try:
                        data = self.system_audio_stream.read(self.chunk, exception_on_overflow=False)
                        
                        # Check if there's actual audio
                        audio_level = np.max(np.abs(np.frombuffer(data, dtype=np.int16)))
                        if audio_level > 100:  # Only send if there's sound
                            if self.system_audio_queue.qsize() < 10:  # Prevent buildup
                                self.system_audio_queue.put(data)
                    except Exception as e:
                        if "Input overflowed" not in str(e):  # Ignore overflow errors
                            print(f"System audio read error: {e}")
                
                # Capture microphone (if in talk mode)
                if (self.mic_stream and 
                    self.call_mode in ["talk", "both"]):
                    try:
                        data = self.mic_stream.read(self.chunk, exception_on_overflow=False)
                        
                        # Check if there's actual audio (voice detection)
                        audio_level = np.max(np.abs(np.frombuffer(data, dtype=np.int16)))
                        if audio_level > 300:  # Voice threshold
                            if self.mic_audio_queue.qsize() < 10:  # Prevent buildup
                                self.mic_audio_queue.put(data)
                                # Debug: Show when microphone is capturing
                                if self.mic_audio_queue.qsize() % 10 == 1:  # Every 10th packet
                                    print(f"🎤 Mic audio captured (level: {audio_level}) - Mode: {self.call_mode}")
                                    
                    except Exception as e:
                        if "Input overflowed" not in str(e):  # Ignore overflow errors
                            print(f"Microphone read error: {e}")
                
                # Play viewer audio
                if not self.viewer_audio_queue.empty() and self.speaker_stream:
                    try:
                        viewer_audio = self.viewer_audio_queue.get_nowait()
                        self.speaker_stream.write(viewer_audio)
                        print("🔊 Playing viewer audio")
                    except queue.Empty:
                        pass
                    except Exception as e:
                        print(f"Speaker output error: {e}")
                
                time.sleep(0.01)  # Small delay
                
            except Exception as e:
                print(f"❌ Audio thread error: {e}")
                time.sleep(0.1)
    
    def set_call_mode(self, mode):
        """Set call mode: off, listen, talk, both"""
        self.call_mode = mode
        print(f"📞 Call mode: {mode}")
    
    def add_viewer_audio(self, audio_data):
        """Add viewer's voice to playback queue"""
        if self.viewer_audio_queue.qsize() < 15:  # Prevent buildup
            self.viewer_audio_queue.put(audio_data)
    
    def get_system_audio(self):
        """Get system audio for sending to viewer"""
        if not self.system_audio_queue.empty():
            try:
                return self.system_audio_queue.get_nowait()
            except queue.Empty:
                pass
        return None
    
    def get_microphone_audio(self):
        """Get microphone audio for sending to viewer"""
        if not self.mic_audio_queue.empty():
            try:
                return self.mic_audio_queue.get_nowait()
            except queue.Empty:
                pass
        return None
    
    def start(self):
        """Start the audio system"""
        self.running = True
        
        print("🎵 Starting Audio-Only Remote Call System")
        self.list_audio_devices()
        
        success = True
        success &= self.start_system_audio_capture()
        success &= self.start_microphone_capture()
        success &= self.start_speaker_output()
        
        if success:
            # Start background audio thread
            threading.Thread(target=self.audio_capture_thread, daemon=True).start()
            print("✅ Audio system ready for calls!")
        else:
            print("❌ Audio system failed to start completely")
        
        return success
    
    def stop(self):
        """Stop the audio system"""
        self.running = False
        
        if self.system_audio_stream:
            self.system_audio_stream.stop_stream()
            self.system_audio_stream.close()
        if self.mic_stream:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
        if self.speaker_stream:
            self.speaker_stream.stop_stream()
            self.speaker_stream.close()
        
        self.p.terminate()
        print("🔇 Audio system stopped")

class AudioCallClient:
    def __init__(self):
        self.uuid = self.get_system_uuid()
        self.websocket = None
        self.running = False
        self.audio_manager = AudioOnlyManager()
        
        # Ping monitoring
        self.last_ping_time = 0
        self.ping_ms = 0
        
    def get_system_uuid(self):
        """Get system UUID"""
        try:
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'uuid'],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and 'UUID' not in line:
                    return line
        except Exception as e:
            print(f"Error getting UUID: {e}")
            return "UNKNOWN-UUID"
    
    async def connect_to_server(self, server_url):
        """Connect to the server"""
        print(f"🔗 Attempting connection to: {server_url}")
        
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            print("🔐 Creating SSL context...")
            
            self.websocket = await websockets.connect(
                server_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            print("🌐 WebSocket connected, sending authentication...")
            
            await self.websocket.send(json.dumps({
                'type': 'audio_client_connect',
                'uuid': self.uuid,
                'client_type': 'audio_only'
            }))
            
            print(f"📡 Connected to server with UUID: {self.uuid}")
            print("✅ Waiting for authentication response...")
            return True
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            print(f"❌ Error type: {type(e).__name__}")
            print(f"❌ Server URL: {server_url}")
            return False
    
    async def handle_messages(self):
        """Handle incoming messages from server"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'call_mode_change':
                    mode = data.get('mode', 'off')
                    self.audio_manager.set_call_mode(mode)
                
                elif msg_type == 'viewer_audio':
                    # Viewer's voice -> play through client speakers
                    try:
                        audio_data = b64decode(data.get('audio'))
                        self.audio_manager.add_viewer_audio(audio_data)
                    except Exception as e:
                        print(f"Error processing viewer audio: {e}")
                
                elif msg_type == 'ping_request':
                    # Respond to ping
                    await self.websocket.send(json.dumps({
                        'type': 'ping_response',
                        'uuid': self.uuid,
                        'timestamp': data.get('timestamp')
                    }))
                
                elif msg_type == 'disconnect':
                    print("📞 Call ended by viewer")
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            print("📞 Connection to server lost")
        except Exception as e:
            print(f"❌ Message handling error: {e}")
    
    async def send_audio_updates(self):
        """Send audio to viewer"""
        while self.running and self.websocket:
            try:
                # Send system audio (Zoom meeting, music, etc.)
                system_audio = self.audio_manager.get_system_audio()
                if system_audio:
                    audio_b64 = b64encode(system_audio).decode('utf-8')
                    await self.websocket.send(json.dumps({
                        'type': 'client_system_audio',
                        'uuid': self.uuid,
                        'audio': audio_b64,
                        'timestamp': time.time()
                    }))
                
                # Send microphone audio (client speaking)
                mic_audio = self.audio_manager.get_microphone_audio()
                if mic_audio:
                    audio_b64 = b64encode(mic_audio).decode('utf-8')
                    await self.websocket.send(json.dumps({
                        'type': 'client_microphone_audio',
                        'uuid': self.uuid,
                        'audio': audio_b64,
                        'timestamp': time.time()
                    }))
                
                await asyncio.sleep(0.03)  # ~33Hz audio updates
                
            except Exception as e:
                print(f"❌ Audio update error: {e}")
                break
    
    async def ping_monitor(self):
        """Monitor connection ping"""
        while self.running and self.websocket:
            try:
                # Send ping request
                ping_time = time.time()
                await self.websocket.send(json.dumps({
                    'type': 'ping_request',
                    'uuid': self.uuid,
                    'timestamp': ping_time
                }))
                
                await asyncio.sleep(5)  # Ping every 5 seconds
                
            except Exception as e:
                print(f"❌ Ping error: {e}")
                break
    
    async def run(self, server_url):
        """Main client loop"""
        if not await self.connect_to_server(server_url):
            return
        
        self.running = True
        
        # Start audio system
        if not self.audio_manager.start():
            print("⚠ Audio system failed to start completely")
            print("Some features may not work")
        
        print("\n📞 AUDIO-ONLY REMOTE CALL CLIENT READY")
        print("=====================================")
        print("Features:")
        print("• System Audio Capture (Zoom meetings, music, etc.)")
        print("• Microphone Capture (your voice)")
        print("• Speaker Output (viewer's voice)")
        print("• Call modes: Off/Listen/Talk/Both")
        print("• Real-time ping monitoring")
        print("\nWaiting for viewer to connect...")
        print("Press Ctrl+C to stop")
        print("=====================================")
        
        try:
            await asyncio.gather(
                self.handle_messages(),
                self.send_audio_updates(),
                self.ping_monitor()
            )
        except KeyboardInterrupt:
            print("\n📞 Call ended by client")
        finally:
            self.running = False
            self.audio_manager.stop()
            if self.websocket:
                await self.websocket.close()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python audio_client.py <server_wss_url>")
        print("Example: python audio_client.py wss://192.168.48.53:5444/ws")
        return
    
    server_url = sys.argv[1]
    client = AudioCallClient()
    
    print("📞 AUDIO-ONLY REMOTE CALL CLIENT")
    print("================================")
    print(f"System UUID: {client.uuid}")
    print(f"Connecting to: {server_url}")
    print("No screen/keyboard/mouse access - Audio only!")
    
    await client.run(server_url)

if __name__ == "__main__":
    asyncio.run(main())