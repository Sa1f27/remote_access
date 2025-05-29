#!/usr/bin/env python3
"""
Remote Desktop Server - WebSocket and HTTP server
Manages client connections, viewer sessions, and UUID validation
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

class Logger:
    def __init__(self, log_file="L_sys_log.txt"):
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
        msg = f"CLIENT CONNECT - UUID: {uuid}, IP: {client_ip}"
        self.logger.info(msg)
    
    def log_client_disconnect(self, uuid, client_ip):
        msg = f"CLIENT DISCONNECT - UUID: {uuid}, IP: {client_ip}"
        self.logger.info(msg)
    
    def log_viewer_connect(self, uuid, viewer_ip):
        msg = f"VIEWER CONNECT - UUID: {uuid}, IP: {viewer_ip}"
        self.logger.info(msg)
    
    def log_viewer_disconnect(self, uuid, viewer_ip):
        msg = f"VIEWER DISCONNECT - UUID: {uuid}, IP: {viewer_ip}"
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
                    print(f"Loaded {len(self.allowed_uuids)} allowed UUIDs")
            else:
                # Create default allowed.json if it doesn't exist
                default_data = {
                    "allowed_uuids": [
                        "EXAMPLE-UUID-1234-5678-9ABC",
                        "EXAMPLE-UUID-ABCD-EFGH-IJKL"
                    ]
                }
                with open(self.allowed_file, 'w') as f:
                    json.dump(default_data, f, indent=2)
                print(f"Created default {self.allowed_file} - Please add your client UUIDs")
                
        except Exception as e:
            print(f"Error loading allowed UUIDs: {e}")
            self.allowed_uuids = set()
    
    def is_allowed(self, uuid):
        """Check if UUID is allowed to connect"""
        return uuid in self.allowed_uuids
    
    def add_uuid(self, uuid):
        """Add UUID to allowed list"""
        self.allowed_uuids.add(uuid)
        self.save_allowed_uuids()
    
    def save_allowed_uuids(self):
        """Save allowed UUIDs to file"""
        try:
            data = {"allowed_uuids": list(self.allowed_uuids)}
            with open(self.allowed_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving allowed UUIDs: {e}")

class ConnectionManager:
    def __init__(self):
        self.clients = {}  # uuid -> {'ws': websocket, 'ip': ip, 'last_seen': timestamp}
        self.viewers = {}  # uuid -> {'ws': websocket, 'ip': ip, 'last_seen': timestamp}
        self.client_stats = {}  # uuid -> {'latency': ms, 'fps': fps}
    
    def add_client(self, uuid, websocket, client_ip):
        """Add client connection"""
        self.clients[uuid] = {
            'ws': websocket,
            'ip': client_ip,
            'last_seen': time.time(),
            'connected_at': time.time()
        }
        self.client_stats[uuid] = {
            'latency': 0,
            'fps': 0,
            'last_frame_time': time.time()
        }
    
    def add_viewer(self, uuid, websocket, viewer_ip):
        """Add viewer connection"""
        self.viewers[uuid] = {
            'ws': websocket,
            'ip': viewer_ip,
            'last_seen': time.time(),
            'connected_at': time.time()
        }
    
    def remove_client(self, uuid):
        """Remove client connection"""
        if uuid in self.clients:
            del self.clients[uuid]
        if uuid in self.client_stats:
            del self.client_stats[uuid]
    
    def remove_viewer(self, uuid):
        """Remove viewer connection"""
        if uuid in self.viewers:
            del self.viewers[uuid]
    
    def get_client(self, uuid):
        """Get client connection by UUID"""
        return self.clients.get(uuid)
    
    def get_viewer(self, uuid):
        """Get viewer connection by UUID"""
        return self.viewers.get(uuid)
    
    def update_client_stats(self, uuid, screen_timestamp):
        """Update client statistics"""
        if uuid in self.client_stats:
            current_time = time.time()
            latency = (current_time - screen_timestamp) * 1000  # ms
            
            stats = self.client_stats[uuid]
            stats['latency'] = latency
            
            # Calculate FPS
            frame_interval = current_time - stats['last_frame_time']
            if frame_interval > 0:
                stats['fps'] = 1.0 / frame_interval
            stats['last_frame_time'] = current_time
    
    def get_connection_status(self, uuid):
        """Get connection status for UUID"""
        client = self.clients.get(uuid)
        viewer = self.viewers.get(uuid)
        stats = self.client_stats.get(uuid, {})
        
        return {
            'client_connected': client is not None,
            'viewer_connected': viewer is not None,
            'client_ip': client['ip'] if client else None,
            'viewer_ip': viewer['ip'] if viewer else None,
            'latency': stats.get('latency', 0),
            'fps': stats.get('fps', 0),
            'uptime': time.time() - client['connected_at'] if client else 0
        }

class RemoteDesktopServer:
    def __init__(self):
        self.logger = Logger()
        self.uuid_validator = UUIDValidator()
        self.connection_manager = ConnectionManager()
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup HTTP routes and WebSocket endpoint"""
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/', self.serve_landing_page)
        self.app.router.add_get('/land.html', self.serve_landing_page)
        self.app.router.add_get('/view.html', self.serve_view_page)
        self.app.router.add_get('/api/status/{uuid}', self.api_connection_status)
        self.app.router.add_static('/', path='static', name='static')
    
    async def serve_landing_page(self, request):
        try:
            async with aiofiles.open('land.html', 'rb') as f:
                content = await f.read()
            return web.Response(body=content, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="Landing page not found", status=404)



    # async def serve_view_page(self, request):
    #     try:
    #         async with aiofiles.open('view.html', 'rb') as f:
    #             content = await f.read()
    #         return web.Response(body=content, content_type='text/html')
    #     except FileNotFoundError:
    #         return web.Response(text="View page not found", status=404)

    async def serve_view_page(self, request):
        try:
            async with aiofiles.open('view.html', 'rb') as f:
                content = await f.read()
            return web.Response(body=content, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="View page not found", status=404)



    
    async def api_connection_status(self, request):
        """API endpoint for connection status"""
        uuid = request.match_info['uuid']
        status = self.connection_manager.get_connection_status(uuid)
        return web.json_response(status)
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
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
                        
                        if msg_type == 'client_connect':
                            uuid = data.get('uuid')
                            if not self.uuid_validator.is_allowed(uuid):
                                await ws.send_str(json.dumps({
                                    'type': 'error',
                                    'message': 'UUID not authorized'
                                }))
                                await ws.close()
                                break
                            
                            connection_type = 'client'
                            self.connection_manager.add_client(uuid, ws, client_ip)
                            self.logger.log_client_connect(uuid, client_ip)
                            
                            await ws.send_str(json.dumps({
                                'type': 'connected',
                                'message': 'Client connected successfully'
                            }))
                        
                        elif msg_type == 'viewer_connect':
                            uuid = data.get('uuid')
                            if not self.uuid_validator.is_allowed(uuid):
                                await ws.send_str(json.dumps({
                                    'type': 'error',
                                    'message': 'UUID not authorized'
                                }))
                                await ws.close()
                                break
                            
                            connection_type = 'viewer'
                            self.connection_manager.add_viewer(uuid, ws, client_ip)
                            self.logger.log_viewer_connect(uuid, client_ip)
                            
                            await ws.send_str(json.dumps({
                                'type': 'connected',
                                'message': 'Viewer connected successfully'
                            }))
                        
                        elif msg_type == 'screen_update':
                            # Forward screen update to viewer
                            uuid = data.get('uuid')
                            viewer = self.connection_manager.get_viewer(uuid)
                            if viewer:
                                await viewer['ws'].send_str(msg.data)
                            
                            # Update client statistics
                            screen_timestamp = data.get('timestamp', time.time())
                            self.connection_manager.update_client_stats(uuid, screen_timestamp)
                        
                        elif msg_type == 'audio_update':
                            # Forward audio update to viewer
                            uuid = data.get('uuid')
                            viewer = self.connection_manager.get_viewer(uuid)
                            if viewer:
                                await viewer['ws'].send_str(msg.data)
                        
                        elif msg_type == 'viewer_audio':
                            # Forward viewer audio to client
                            uuid = data.get('uuid')
                            client = self.connection_manager.get_client(uuid)
                            if client:
                                await client['ws'].send_str(msg.data)
                        
                        elif msg_type == 'audio_mode_change':
                            # Forward audio mode change to client
                            uuid = data.get('uuid')
                            client = self.connection_manager.get_client(uuid)
                            if client:
                                await client['ws'].send_str(msg.data)
                        
                        elif msg_type == 'mouse_event':
                            # Forward mouse event to client
                            uuid = data.get('uuid')
                            client = self.connection_manager.get_client(uuid)
                            if client:
                                await client['ws'].send_str(msg.data)
                        
                        elif msg_type == 'keyboard_event':
                            # Forward keyboard event to client
                            uuid = data.get('uuid')
                            client = self.connection_manager.get_client(uuid)
                            if client:
                                await client['ws'].send_str(msg.data)
                        
                        elif msg_type == 'ping':
                            await ws.send_str(json.dumps({
                                'type': 'pong',
                                'timestamp': time.time()
                            }))
                    
                    except json.JSONDecodeError:
                        self.logger.log_error(f"Invalid JSON from {client_ip}")
                        continue
                
                elif msg.type == WSMsgType.ERROR:
                    self.logger.log_error(f'WebSocket error: {ws.exception()}')
        
        except Exception as e:
            self.logger.log_error(f"WebSocket handler error: {e}")
        
        finally:
            # Clean up connection
            if connection_type == 'client' and uuid:
                self.connection_manager.remove_client(uuid)
                self.logger.log_client_disconnect(uuid, client_ip)
            elif connection_type == 'viewer' and uuid:
                self.connection_manager.remove_viewer(uuid)
                self.logger.log_viewer_disconnect(uuid, client_ip)
        
        return ws
    
    def create_ssl_context(self, cert_file, key_file):
        """Create SSL context for HTTPS/WSS"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)
        return ssl_context
    
    async def start_server(self, host='0.0.0.0', port=5444, cert_file=None, key_file=None):
        """Start the server"""
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
        
        print(f"Remote Desktop Server started")
        print(f"Web Interface: {scheme}://{host}:{port}")
        print(f"WebSocket: {ws_scheme}://{host}:{port}/ws")
        print(f"Allowed UUIDs: {len(self.uuid_validator.allowed_uuids)}")
        
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            print("Server shutdown requested")
        finally:
            await runner.cleanup()

def main():
    import argparse
    # 192.168.48.201
    parser = argparse.ArgumentParser(description='Remote Desktop Server')
    parser.add_argument('--host', default='192.168.48.201', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5444, help='Port to bind to')
    parser.add_argument('--cert', help='SSL certificate file')
    parser.add_argument('--key', help='SSL private key file')
    
    args = parser.parse_args()
    
    server = RemoteDesktopServer()
    
    print("Starting Remote Desktop Server...")
    print(f"Logs will be written to: L_sys_log.txt")
    print(f"UUID validation file: allowed.json")
    
    asyncio.run(server.start_server(
        host=args.host,
        port=args.port,
        cert_file=args.cert,
        key_file=args.key
    ))

if __name__ == "__main__":
    main()