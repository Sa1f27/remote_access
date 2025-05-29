#!/usr/bin/env python3
"""
Remote Desktop Client - Headless screen sharing and audio capture
Captures screen and system audio, streams to server via WebSocket
"""

import asyncio
import json
import ssl
import subprocess
import sys
import time
import threading
import queue
from base64 import b64encode
from io import BytesIO

import websockets
import pyaudio
import mss
import numpy as np
from PIL import Image
import pynput
from pynput import mouse, keyboard

class AudioManager:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.audio_queue = queue.Queue()
        self.viewer_audio_queue = queue.Queue()
        self.mixed_audio_queue = queue.Queue()
        self.audio_mode = "client_only"  # client_only, viewer_only, merged
        self.running = False
        
        # Audio settings for low latency
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024
        
    def get_audio_devices(self):
        devices = []
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            devices.append({
                'index': i,
                'name': info['name'],
                'channels': info['maxInputChannels']
            })
        return devices
    
    def start_system_audio_capture(self):
        try:
            wasapi_info = None
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                name_lower = info['name'].lower()
                # Look for WASAPI loopback device first
                if "wasapi" in name_lower and "loopback" in name_lower:
                    wasapi_info = info
                    break
            
            if not wasapi_info:
                # Fallback: look for Stereo Mix device
                for i in range(self.p.get_device_count()):
                    info = self.p.get_device_info_by_index(i)
                    if "stereo mix" in info['name'].lower():
                        wasapi_info = info
                        break
            
            if not wasapi_info:
                print("Warning: No WASAPI loopback or Stereo Mix device found, using default input")
                device_index = None
            else:
                device_index = wasapi_info['index']
            
            self.input_stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk,
                stream_callback=self._audio_callback
            )
            self.input_stream.start_stream()
            print(f"Started system audio capture on device: {wasapi_info['name'] if wasapi_info else 'Default'}")
            
        except Exception as e:
            print(f"Error starting system audio capture: {e}")
    def start_microphone_output(self):
        """Output mixed audio to microphone (for WebCall injection)"""
        try:
            # Find default microphone output device
            default_output = self.p.get_default_output_device_info()
            
            self.output_stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                output=True,
                output_device_index=default_output['index'],
                frames_per_buffer=self.chunk
            )
            print(f"Started microphone output to: {default_output['name']}")
            
        except Exception as e:
            print(f"Error starting microphone output: {e}")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for system audio capture"""
        if self.running:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def add_viewer_audio(self, audio_data):
        if self.viewer_audio_queue.qsize() > 20:
            try:
                self.viewer_audio_queue.get_nowait()  # drop oldest
            except queue.Empty:
                pass
        print(f"Adding viewer audio of size {len(audio_data)} bytes to queue")
        print()
        self.viewer_audio_queue.put(audio_data)

    
    def set_audio_mode(self, mode):
        """Set audio routing mode"""
        self.audio_mode = mode
        print(f"Audio mode changed to: {mode}")
    
    def start_audio_mixer(self):
        def mixer_thread():
            while self.running:
                try:
                    mixed_audio = None
                    
                    if self.audio_mode == "client_only":
                        # Only system audio
                        if not self.audio_queue.empty():
                            system_audio = self.audio_queue.get_nowait()
                            mixed_audio = system_audio
                    
                    elif self.audio_mode == "viewer_only":
                        # Only viewer audio
                        if not self.viewer_audio_queue.empty():
                            viewer_audio = self.viewer_audio_queue.get_nowait()
                            mixed_audio = viewer_audio
                    
                    elif self.audio_mode == "merged":
                        system_audio = None
                        viewer_audio = None
                        
                        if not self.audio_queue.empty():
                            system_audio = self.audio_queue.get_nowait()
                        if not self.viewer_audio_queue.empty():
                            viewer_audio = self.viewer_audio_queue.get_nowait()
                        
                        if system_audio and viewer_audio:
                            sys_np = np.frombuffer(system_audio, dtype=np.int16)
                            viewer_np = np.frombuffer(viewer_audio, dtype=np.int16)
                            min_len = min(len(sys_np), len(viewer_np))
                            mixed_np = (sys_np[:min_len] * 0.5 + viewer_np[:min_len] * 0.5).astype(np.int16)
                            mixed_audio = mixed_np.tobytes()
                        elif viewer_audio:
                            mixed_audio = viewer_audio
                        elif system_audio:
                            mixed_audio = system_audio
                    
                    if mixed_audio and self.output_stream:
                        self.output_stream.write(mixed_audio)
                        print(f"Playing audio chunk of size {len(mixed_audio)} bytes")
                    else:
                        # To avoid blocking if no audio, sleep a bit
                        time.sleep(0.005)
                    
                except queue.Empty:
                    time.sleep(0.005)
                    continue
                except Exception as e:
                    print(f"Audio mixer error: {e}")
                    time.sleep(0.01)
        
        threading.Thread(target=mixer_thread, daemon=True).start()

    
    def start(self):
        self.running = True
        self.start_system_audio_capture()
        self.start_microphone_output()
        self.start_audio_mixer()
    
    def stop(self):
        self.running = False
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        self.p.terminate()

class ScreenCapture:
    def __init__(self):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]  # Primary monitor
        
    def capture_screen(self, quality=85):
        """Capture screen and return compressed JPEG data"""
        try:
            screenshot = self.sct.grab(self.monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # Compress image
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            buffer.seek(0)
            
            return b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"Screen capture error: {e}")
            return None

class InputController:
    def __init__(self):
        self.mouse_controller = pynput.mouse.Controller()
        self.keyboard_controller = pynput.keyboard.Controller()
        
    def handle_mouse_event(self, event_data):
        """Handle mouse events from viewer"""
        try:
            event_type = event_data.get('type')
            x = event_data.get('x', 0)
            y = event_data.get('y', 0)
            
            if event_type == 'move':
                self.mouse_controller.position = (x, y)
            elif event_type == 'click':
                button = mouse.Button.left if event_data.get('button') == 'left' else mouse.Button.right
                self.mouse_controller.click(button)
            elif event_type == 'scroll':
                dx = event_data.get('dx', 0)
                dy = event_data.get('dy', 0)
                self.mouse_controller.scroll(dx, dy)
                
        except Exception as e:
            print(f"Mouse event error: {e}")
    
    def handle_keyboard_event(self, event_data):
        """Handle keyboard events from viewer"""
        try:
            event_type = event_data.get('type')
            key = event_data.get('key')
            
            if event_type == 'press':
                self.keyboard_controller.press(key)
            elif event_type == 'release':
                self.keyboard_controller.release(key)
                
        except Exception as e:
            print(f"Keyboard event error: {e}")

class RemoteDesktopClient:
    def __init__(self):
        self.uuid = self.get_system_uuid()
        self.websocket = None
        self.running = False
        self.audio_manager = AudioManager()
        self.screen_capture = ScreenCapture()
        self.input_controller = InputController()
        
    def get_system_uuid(self):
        """Get system UUID using wmic command"""
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
        """Connect to the remote desktop server"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            self.websocket = await websockets.connect(
                server_url,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10
            )
            
            # Send initial connection with UUID
            await self.websocket.send(json.dumps({
                'type': 'client_connect',
                'uuid': self.uuid
            }))
            
            print(f"Connected to server with UUID: {self.uuid}")
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    async def handle_messages(self):
        """Handle incoming messages from server"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'audio_mode_change':
                    self.audio_manager.set_audio_mode(data.get('mode'))
                
                elif msg_type == 'viewer_audio':
                    # Decode and add viewer audio to mixer
                    import base64
                    audio_data = base64.b64decode(data.get('audio'))
                    self.audio_manager.add_viewer_audio(audio_data)
                
                elif msg_type == 'mouse_event':
                    self.input_controller.handle_mouse_event(data.get('event'))
                
                elif msg_type == 'keyboard_event':
                    self.input_controller.handle_keyboard_event(data.get('event'))
                
                elif msg_type == 'disconnect':
                    print("Server requested disconnect")
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            print("Connection to server lost")
        except Exception as e:
            print(f"Message handling error: {e}")
    
    async def send_screen_updates(self):
        """Send screen updates to server"""
        frame_time = 1.0 / 25  # 25 FPS
        
        while self.running and self.websocket:
            try:
                start_time = time.time()
                
                # Capture and send screen
                screen_data = self.screen_capture.capture_screen()
                if screen_data:
                    await self.websocket.send(json.dumps({
                        'type': 'screen_update',
                        'uuid': self.uuid,
                        'screen': screen_data,
                        'timestamp': time.time()
                    }))
                
                # Maintain frame rate
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_time - elapsed)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                print(f"Screen update error: {e}")
                break
    
    async def send_audio_updates(self):
        """Send system audio to server"""
        while self.running and self.websocket:
            try:
                if not self.audio_manager.audio_queue.empty():
                    audio_data = self.audio_manager.audio_queue.get_nowait()
                    audio_b64 = b64encode(audio_data).decode('utf-8')
                    
                    await self.websocket.send(json.dumps({
                        'type': 'audio_update',
                        'uuid': self.uuid,
                        'audio': audio_b64,
                        'timestamp': time.time()
                    }))
                
                await asyncio.sleep(0.02)  # 50Hz audio updates
                
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Audio update error: {e}")
                break
    
    async def run(self, server_url):
        """Main client loop"""
        if not await self.connect_to_server(server_url):
            return
        
        self.running = True
        self.audio_manager.start()
        
        try:
            # Run all tasks concurrently
            await asyncio.gather(
                self.handle_messages(),
                self.send_screen_updates(),
                self.send_audio_updates()
            )
        except KeyboardInterrupt:
            print("Client shutdown requested")
        finally:
            self.running = False
            self.audio_manager.stop()
            if self.websocket:
                await self.websocket.close()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <server_wss_url>")
        print("Example: python client.py wss://your-server.com:5444/ws")
        return
    
    server_url = sys.argv[1]
    client = RemoteDesktopClient()
    
    print(f"Starting Remote Desktop Client")
    print(f"System UUID: {client.uuid}")
    print(f"Connecting to: {server_url}")
    
    await client.run(server_url)

if __name__ == "__main__":
    asyncio.run(main())