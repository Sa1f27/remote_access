#!/usr/bin/env python3
"""
Audio-Only Remote Call Server
Handles only audio communication - no screen/keyboard/mouse
"""

import asyncio
import json
import ssl
import time
import logging
from datetime import datetime
from pathlib import Path

import aiohttp
from aiohttp import web, WSMsgType
import aiofiles

class AudioCallLogger:
    def __init__(self, log_file="audio_call_log.txt"):
        self.log_file = log_file
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log_client_connect(self, uuid, client_ip):
        msg = f"AUDIO CLIENT CONNECT - UUID: {uuid}, IP: {client_ip}"
        self.logger.info(msg)
    
    def log_client_disconnect(self, uuid, client_ip):
        msg = f"AUDIO CLIENT DISCONNECT - UUID: {uuid}, IP: {client_ip}"
        self.logger.info(msg)
    
    def log_viewer_connect(self, uuid, viewer_ip):
        msg = f"AUDIO VIEWER CONNECT - UUID: {uuid}, IP: {viewer_ip}"
        self.logger.info(msg)
    
    def log_viewer_disconnect(self, uuid, viewer_ip):
        msg = f"AUDIO VIEWER DISCONNECT - UUID: {uuid}, IP: {viewer_ip}"
        self.logger.info(msg)
    
    def log_call_mode_change(self, uuid, mode):
        msg = f"CALL MODE CHANGE - UUID: {uuid}, Mode: {mode}"
        self.logger.info(msg)
    
    def log_audio_stats(self, uuid, system_audio_count, mic_audio_count):
        msg = f"AUDIO STATS - UUID: {uuid}, System: {system_audio_count}, Mic: {mic_audio_count}"
        self.logger.info(msg)
    
    def log_error(self, error_msg):
        self.logger.error(error_msg)

class UUIDValidator:
    def __init__(self, allowed_file="allowed.json"):
        self.allowed_file = allowed_file
        self.allowed_uuids = set()
        self.load_allowed_uuids()
    
    def load_allowed_uuids(self):
        """Load allowed UUIDs from JSON file"""
        try:
            if Path(self.allowed_file).exists():
                with open(self.allowed_file, 'r') as f:
                    data = json.load(f)
                    self.allowed_uuids = set(data.get('allowed_uuids', []))
                    print(f"📋 Loaded {len(self.allowed_uuids)} allowed UUIDs")
            else:
                # Create default allowed.json
                default_data = {
                    "allowed_uuids": [
                        "EXAMPLE-UUID-1234-5678-9ABC",
                        "YOUR-CLIENT-UUID-HERE"
                    ]
                }
                with open(self.allowed_file, 'w') as f:
                    json.dump(default_data, f, indent=2)
                print(f"📋 Created default {self.allowed_file} - Please add your client UUIDs")
                
        except Exception as e:
            print(f"❌ Error loading allowed UUIDs: {e}")
            self.allowed_uuids = set()
    
    def is_allowed(self, uuid):
        """Check if UUID is allowed to connect"""
        return uuid in self.allowed_uuids

class AudioCallManager:
    def __init__(self):
        self.audio_clients = {}  # uuid -> {'ws': websocket, 'ip': ip, 'connected_at': time}
        self.audio_viewers = {}  # uuid -> {'ws': websocket, 'ip': ip, 'connected_at': time}
        self.call_modes = {}     # uuid -> call_mode (off, listen, talk, both)
        self.ping_times = {}     # uuid -> last_ping_time
        self.audio_stats = {}    # uuid -> {'system_audio': count, 'mic_audio': count}
    
    def add_audio_client(self, uuid, websocket, client_ip):
        """Add audio client connection"""
        self.audio_clients[uuid] = {
            'ws': websocket,
            'ip': client_ip,
            'connected_at': time.time()
        }
        self.call_modes[uuid] = 'off'
        self.audio_stats[uuid] = {'system_audio': 0, 'mic_audio': 0}
    
    def add_audio_viewer(self, uuid, websocket, viewer_ip):
        """Add audio viewer connection"""
        self.audio_viewers[uuid] = {
            'ws': websocket,
            'ip': viewer_ip,
            'connected_at': time.time()
        }
    
    def remove_audio_client(self, uuid):
        """Remove audio client connection"""
        if uuid in self.audio_clients:
            del self.audio_clients[uuid]
        if uuid in self.call_modes:
            del self.call_modes[uuid]
        if uuid in self.ping_times:
            del self.ping_times[uuid]
        if uuid in self.audio_stats:
            del self.audio_stats[uuid]
    
    def remove_audio_viewer(self, uuid):
        """Remove audio viewer connection"""
        if uuid in self.audio_viewers:
            del self.audio_viewers[uuid]
    
    def get_audio_client(self, uuid):
        """Get audio client connection by UUID"""
        return self.audio_clients.get(uuid)
    
    def get_audio_viewer(self, uuid):
        """Get audio viewer connection by UUID"""
        return self.audio_viewers.get(uuid)
    
    def set_call_mode(self, uuid, mode):
        """Set call mode for a UUID"""
        self.call_modes[uuid] = mode
    
    def get_call_mode(self, uuid):
        """Get current call mode for a UUID"""
        return self.call_modes.get(uuid, 'off')
    
    def update_ping(self, uuid):
        """Update last ping time"""
        self.ping_times[uuid] = time.time()
    
    def update_audio_stats(self, uuid, audio_type):
        """Update audio statistics"""
        if uuid in self.audio_stats:
            self.audio_stats[uuid][audio_type] += 1
    
    def get_connection_status(self, uuid):
        """Get connection status for UUID"""
        client = self.audio_clients.get(uuid)
        viewer = self.audio_viewers.get(uuid)
        stats = self.audio_stats.get(uuid, {})
        
        return {
            'audio_client_connected': client is not None,
            'audio_viewer_connected': viewer is not None,
            'client_ip': client['ip'] if client else None,
            'viewer_ip': viewer['ip'] if viewer else None,
            'call_mode': self.get_call_mode(uuid),
            'system_audio_count': stats.get('system_audio', 0),
            'mic_audio_count': stats.get('mic_audio', 0),
            'uptime': time.time() - client['connected_at'] if client else 0
        }

class AudioOnlyServer:
    def __init__(self):
        self.logger = AudioCallLogger()
        self.uuid_validator = UUIDValidator()
        self.call_manager = AudioCallManager()
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup HTTP routes and WebSocket endpoint"""
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/', self.serve_landing_page)
        self.app.router.add_get('/land.html', self.serve_landing_page)
        self.app.router.add_get('/view.html', self.serve_audio_viewer)
        self.app.router.add_get('/audio_call.html', self.serve_audio_viewer)
        self.app.router.add_get('/api/status/{uuid}', self.api_connection_status)
        self.app.router.add_static('/', path='static', name='static')
    
    async def serve_landing_page(self, request):
        try:
            async with aiofiles.open('land.html', 'rb') as f:
                content = await f.read()
            return web.Response(body=content, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="Landing page not found", status=404)

    async def serve_audio_viewer(self, request):
        try:
            # Serve view.html (your audio-only viewer)
            async with aiofiles.open('view.html', 'rb') as f:
                content = await f.read()
            return web.Response(body=content, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="view.html not found - Please save the Audio-Only Remote Call Viewer as 'view.html'", status=404)
    
    async def api_connection_status(self, request):
        """API endpoint for connection status"""
        uuid = request.match_info['uuid']
        status = self.call_manager.get_connection_status(uuid)
        return web.json_response(status)
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections - Audio Only"""
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        
        client_ip = request.remote
        connection_type = None
        uuid = None
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get('type')
                        
                        if msg_type == 'audio_client_connect':
                            uuid = data.get('uuid')
                            if not self.uuid_validator.is_allowed(uuid):
                                await ws.send_str(json.dumps({
                                    'type': 'error',
                                    'message': 'UUID not authorized for audio calls'
                                }))
                                await ws.close()
                                break
                            
                            connection_type = 'audio_client'
                            self.call_manager.add_audio_client(uuid, ws, client_ip)
                            self.logger.log_client_connect(uuid, client_ip)
                            
                            await ws.send_str(json.dumps({
                                'type': 'connected',
                                'message': 'Audio client connected successfully'
                            }))
                        
                        elif msg_type == 'audio_viewer_connect':
                            uuid = data.get('uuid')
                            if not self.uuid_validator.is_allowed(uuid):
                                await ws.send_str(json.dumps({
                                    'type': 'error',
                                    'message': 'UUID not authorized for audio calls'
                                }))
                                await ws.close()
                                break
                            
                            connection_type = 'audio_viewer'
                            self.call_manager.add_audio_viewer(uuid, ws, client_ip)
                            self.logger.log_viewer_connect(uuid, client_ip)
                            
                            await ws.send_str(json.dumps({
                                'type': 'connected',
                                'message': 'Audio viewer connected successfully'
                            }))
                        
                        elif msg_type == 'client_system_audio':
                            # Client's system audio (Zoom, music, etc.) -> Forward to viewer
                            uuid = data.get('uuid')
                            call_mode = self.call_manager.get_call_mode(uuid)
                            
                            if call_mode in ['listen', 'both']:
                                viewer = self.call_manager.get_audio_viewer(uuid)
                                if viewer:
                                    await viewer['ws'].send_str(msg.data)
                                    self.call_manager.update_audio_stats(uuid, 'system_audio')
                        
                        elif msg_type == 'client_microphone_audio':
                            # Client's microphone -> Forward to viewer 
                            uuid = data.get('uuid')
                            call_mode = self.call_manager.get_call_mode(uuid)
                            
                            # Forward client mic in LISTEN and BOTH modes (so viewer can always hear client)
                            if call_mode in ['listen', 'both']:
                                viewer = self.call_manager.get_audio_viewer(uuid)
                                if viewer:
                                    await viewer['ws'].send_str(msg.data)
                                    self.call_manager.update_audio_stats(uuid, 'mic_audio')
                        
                        elif msg_type == 'viewer_audio':
                            # Viewer's microphone -> Forward to client
                            uuid = data.get('uuid')
                            call_mode = self.call_manager.get_call_mode(uuid)
                            
                            if call_mode in ['talk', 'both']:
                                client = self.call_manager.get_audio_client(uuid)
                                if client:
                                    await client['ws'].send_str(msg.data)
                        
                        elif msg_type == 'call_mode_change':
                            # Update call mode and forward to client
                            uuid = data.get('uuid')
                            mode = data.get('mode', 'off')
                            
                            self.call_manager.set_call_mode(uuid, mode)
                            self.logger.log_call_mode_change(uuid, mode)
                            
                            # Forward mode change to client
                            client = self.call_manager.get_audio_client(uuid)
                            if client:
                                await client['ws'].send_str(msg.data)
                        
                        elif msg_type == 'ping_request':
                            # Handle ping from viewer to client
                            uuid = data.get('uuid')
                            client = self.call_manager.get_audio_client(uuid)
                            if client:
                                await client['ws'].send_str(msg.data)
                        
                        elif msg_type == 'ping_response':
                            # Handle ping response from client to viewer
                            uuid = data.get('uuid')
                            viewer = self.call_manager.get_audio_viewer(uuid)
                            if viewer:
                                await viewer['ws'].send_str(msg.data)
                            
                            self.call_manager.update_ping(uuid)
                        
                        elif msg_type == 'disconnect':
                            print(f"📞 Call ended for UUID: {uuid}")
                            break
                    
                    except json.JSONDecodeError:
                        self.logger.log_error(f"Invalid JSON from {client_ip}")
                        continue
                
                elif msg.type == WSMsgType.ERROR:
                    self.logger.log_error(f'WebSocket error: {ws.exception()}')
        
        except Exception as e:
            self.logger.log_error(f"WebSocket handler error: {e}")
        
        finally:
            # Clean up connection
            if connection_type == 'audio_client' and uuid:
                # Log final audio stats
                stats = self.call_manager.audio_stats.get(uuid, {})
                self.logger.log_audio_stats(
                    uuid, 
                    stats.get('system_audio', 0), 
                    stats.get('mic_audio', 0)
                )
                
                self.call_manager.remove_audio_client(uuid)
                self.logger.log_client_disconnect(uuid, client_ip)
                
            elif connection_type == 'audio_viewer' and uuid:
                self.call_manager.remove_audio_viewer(uuid)
                self.logger.log_viewer_disconnect(uuid, client_ip)
        
        return ws
    
    def create_ssl_context(self, cert_file, key_file):
        """Create SSL context for HTTPS/WSS"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)
        return ssl_context
    
    async def start_server(self, host='0.0.0.0', port=5444, cert_file=None, key_file=None):
        """Start the audio-only server"""
        if cert_file and key_file:
            ssl_context = self.create_ssl_context(cert_file, key_file)
            scheme = "https"
            ws_scheme = "wss"
        else:
            ssl_context = None
            scheme = "http"
            ws_scheme = "ws"
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port, ssl_context=ssl_context)
        await site.start()
        
        print("📞" + "="*60)
        print("   AUDIO-ONLY REMOTE CALL SERVER STARTED")
        print("="*62)
        print(f"🌐 Web Interface: {scheme}://{host}:{port}")
        print(f"📡 WebSocket: {ws_scheme}://{host}:{port}/ws")
        print(f"📋 Allowed UUIDs: {len(self.uuid_validator.allowed_uuids)}")
        print(f"🎤 Features: System Audio + Microphone + Call Modes")
        print(f"📊 Logs: audio_call_log.txt")
        print("="*62)
        print("🎵 CALL MODES:")
        print("  • Off: No audio transmission")
        print("  • Listen: Hear client's system audio (Zoom, music, etc.)")
        print("  • Talk: Send your voice to client")
        print("  • Both: Full two-way conversation")
        print("="*62)
        print("🚀 Ready for audio calls!")
        
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            print("\n📞 Audio call server shutdown requested")
        finally:
            await runner.cleanup()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Audio-Only Remote Call Server')
    parser.add_argument('--host', default='192.168.48.53', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5444, help='Port to bind to')
    parser.add_argument('--cert', help='SSL certificate file')
    parser.add_argument('--key', help='SSL private key file')
    
    args = parser.parse_args()
    
    server = AudioOnlyServer()
    
    print("🎵 Starting Audio-Only Remote Call Server...")
    print(f"📝 Call logs: audio_call_log.txt")
    print(f"🔐 UUID validation: allowed.json")
    print("🎯 No screen/keyboard/mouse - Pure audio communication!")
    
    asyncio.run(server.start_server(
        host=args.host,
        port=args.port,
        cert_file=args.cert,
        key_file=args.key
    ))

if __name__ == "__main__":
    main()