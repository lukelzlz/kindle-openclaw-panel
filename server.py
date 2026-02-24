#!/usr/bin/env python3
"""
OpenClaw Kindle Panel Server - CORS 代理 + WebSocket 代理
用法: python3 server.py [port] [gateway_url]
默认: port=8080, gateway_url=http://127.0.0.1:7860

功能:
1. 静态文件服务（index.html）
2. HTTP 代理（转发 /v1/ 和 /tools/ 请求到 Gateway）
3. WebSocket 代理（转发 /ws 请求到 Gateway WebSocket）
"""

import http.server
import urllib.request
import urllib.error
import sys
import os
import socket
import select
import struct
import hashlib
import base64
import json
from threading import Thread

# 启用系统代理支持
import os
proxy_handler = urllib.request.ProxyHandler(urllib.request.getproxies())
opener = urllib.request.build_opener(proxy_handler)
urllib.request.install_opener(opener)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
GATEWAY = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:7860"
GATEWAY_WS = GATEWAY.replace("http://", "ws://").replace("https://", "wss://")

# WebSocket 魔数
WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def compute_accept_key(key):
    """计算 WebSocket Sec-WebSocket-Accept 值"""
    sha1 = hashlib.sha1((key + WS_MAGIC).encode()).digest()
    return base64.b64encode(sha1).decode()


def create_ws_frame(data, opcode=0x01):
    """创建 WebSocket 帧（opcode=0x01 文本帧）"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    length = len(data)
    frame = bytearray()
    
    # FIN + opcode
    frame.append(0x80 | opcode)
    
    # Payload length
    if length <= 125:
        frame.append(0x80 | length)  # MASK=1
    elif length <= 65535:
        frame.append(0x80 | 126)
        frame.extend(struct.pack('>H', length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack('>Q', length))
    
    # Masking key
    import random
    mask = bytes([random.randint(0, 255) for _ in range(4)])
    frame.extend(mask)
    
    # Masked payload
    masked_data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    frame.extend(masked_data)
    
    return bytes(frame)


def parse_ws_frame(data):
    """解析 WebSocket 帧，返回 (opcode, payload, offset)"""
    if len(data) < 2:
        return None, None, 0
    
    fin = (data[0] & 0x80) != 0
    opcode = data[0] & 0x0F
    masked = (data[1] & 0x80) != 0
    length = data[1] & 0x7F
    
    offset = 2
    
    if length == 126:
        if len(data) < offset + 2:
            return None, None, 0
        length = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
    elif length == 127:
        if len(data) < offset + 8:
            return None, None, 0
        length = struct.unpack('>Q', data[offset:offset+8])[0]
        offset += 8
    
    if masked:
        if len(data) < offset + 4:
            return None, None, 0
        mask = data[offset:offset+4]
        offset += 4
    
    if len(data) < offset + length:
        return None, None, 0
    
    payload = data[offset:offset+length]
    
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    
    return opcode, payload, offset + length


class WebSocketProxy:
    """WebSocket 代理：客户端 <-> 代理 <-> Gateway"""
    
    def __init__(self, client_socket, gateway_url):
        self.client = client_socket
        self.gateway_url = gateway_url
        self.gateway_socket = None
        self.client_buffer = b''
        self.gateway_buffer = b''
        self.client_handshake_done = False
        self.gateway_handshake_done = False
    
    def run(self):
        try:
            # 连接 Gateway WebSocket
            self.connect_to_gateway()
            
            # 主循环
            while True:
                sockets = [self.client]
                if self.gateway_socket:
                    sockets.append(self.gateway_socket)
                
                readable, _, _ = select.select(sockets, [], [], 30)
                
                for sock in readable:
                    if sock is self.client:
                        self.handle_client_data()
                    elif sock is self.gateway_socket:
                        self.handle_gateway_data()
                
                if not sockets:
                    # 超时，检查连接状态
                    pass
                    
        except Exception as e:
            print(f"WebSocket proxy error: {e}")
        finally:
            self.close()
    
    def connect_to_gateway(self):
        """连接到 Gateway WebSocket"""
        # 解析 URL
        if self.gateway_url.startswith('ws://'):
            host_port = self.gateway_url[5:]
            use_ssl = False
        else:
            host_port = self.gateway_url[6:]  # wss://
            use_ssl = True
        
        if '/' in host_port:
            host_port = host_port.split('/')[0]
        
        if ':' in host_port:
            host, port = host_port.rsplit(':', 1)
            port = int(port)
        else:
            host = host_port
            port = 443 if use_ssl else 80
        
        # 创建 socket
        self.gateway_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gateway_socket.settimeout(10)
        self.gateway_socket.connect((host, port))
        
        if use_ssl:
            import ssl
            context = ssl.create_default_context()
            self.gateway_socket = context.wrap_socket(self.gateway_socket, server_hostname=host)
        
        # 发送握手
        key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self.gateway_socket.send(handshake.encode())
        
        # 等待握手响应
        response = b''
        while b'\r\n\r\n' not in response:
            chunk = self.gateway_socket.recv(4096)
            if not chunk:
                raise Exception("Gateway closed connection during handshake")
            response += chunk
        
        self.gateway_handshake_done = True
        print(f"Connected to Gateway WebSocket: {self.gateway_url}")
    
    def handle_client_data(self):
        """处理客户端数据"""
        try:
            data = self.client.recv(4096)
            if not data:
                raise Exception("Client disconnected")
            
            self.client_buffer += data
            
            if not self.client_handshake_done:
                # 处理握手
                if b'\r\n\r\n' in self.client_buffer:
                    self.handle_client_handshake()
            else:
                # 处理 WebSocket 帧
                while self.client_buffer:
                    opcode, payload, offset = parse_ws_frame(self.client_buffer)
                    if offset == 0:
                        break  # 数据不完整
                    
                    self.client_buffer = self.client_buffer[offset:]
                    
                    if opcode == 0x08:  # Close
                        self.send_close_to_gateway()
                        return
                    elif opcode == 0x09:  # Ping
                        self.send_pong_to_client(payload)
                    elif opcode == 0x01 or opcode == 0x02:  # Text or Binary
                        # 转发到 Gateway
                        self.forward_to_gateway(payload, opcode)
                        
        except Exception as e:
            print(f"Client data error: {e}")
            raise
    
    def handle_client_handshake(self):
        """处理客户端 WebSocket 握手"""
        request = self.client_buffer.decode('utf-8', errors='ignore')
        self.client_buffer = b''
        
        # 解析 Sec-WebSocket-Key
        key = None
        for line in request.split('\r\n'):
            if line.lower().startswith('sec-websocket-key:'):
                key = line.split(':', 1)[1].strip()
                break
        
        if not key:
            raise Exception("No Sec-WebSocket-Key in client handshake")
        
        # 发送握手响应
        accept_key = compute_accept_key(key)
        response = (
            f"HTTP/1.1 101 Switching Protocols\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n"
            f"\r\n"
        )
        self.client.send(response.encode())
        self.client_handshake_done = True
        print("Client WebSocket handshake completed")
    
    def handle_gateway_data(self):
        """处理 Gateway 数据"""
        try:
            data = self.gateway_socket.recv(4096)
            if not data:
                raise Exception("Gateway disconnected")
            
            # 直接转发 WebSocket 帧到客户端
            # 注意：Gateway 发送的帧是 unmasked 的，需要直接转发
            self.client.send(data)
            
        except Exception as e:
            print(f"Gateway data error: {e}")
            raise
    
    def forward_to_gateway(self, payload, opcode):
        """转发数据到 Gateway"""
        if self.gateway_socket:
            # 创建 unmasked 帧（服务端不需要 mask）
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            
            length = len(payload)
            frame = bytearray()
            
            # FIN + opcode
            frame.append(0x80 | opcode)
            
            # Payload length (no mask)
            if length <= 125:
                frame.append(length)
            elif length <= 65535:
                frame.append(126)
                frame.extend(struct.pack('>H', length))
            else:
                frame.append(127)
                frame.extend(struct.pack('>Q', length))
            
            frame.extend(payload)
            self.gateway_socket.send(bytes(frame))
    
    def send_pong_to_client(self, payload):
        """发送 Pong 到客户端"""
        frame = create_ws_frame(payload, opcode=0x0A)
        self.client.send(frame)
    
    def send_close_to_gateway(self):
        """发送 Close 到 Gateway"""
        if self.gateway_socket:
            try:
                # Close frame
                frame = bytearray([0x88, 0])
                self.gateway_socket.send(bytes(frame))
            except:
                pass
    
    def close(self):
        """关闭连接"""
        try:
            if self.client:
                self.client.close()
        except:
            pass
        try:
            if self.gateway_socket:
                self.gateway_socket.close()
        except:
            pass


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/ws' or self.path.startswith('/ws?'):
            self.handle_websocket_upgrade()
        elif self.path.startswith('/v1/') or self.path.startswith('/tools/'):
            self.proxy_request()
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path.startswith('/v1/') or self.path.startswith('/tools/'):
            self.proxy_request()
        else:
            self.send_error(404)
    
    def handle_websocket_upgrade(self):
        """处理 WebSocket 升级请求"""
        # 检查是否是 WebSocket 请求
        upgrade = self.headers.get('Upgrade', '').lower()
        connection = self.headers.get('Connection', '').lower()
        
        if upgrade != 'websocket' or 'upgrade' not in connection:
            self.send_error(400, "Expected WebSocket upgrade")
            return
        
        key = self.headers.get('Sec-WebSocket-Key')
        if not key:
            self.send_error(400, "Missing Sec-WebSocket-Key")
            return
        
        # 发送握手响应
        accept_key = compute_accept_key(key)
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept_key)
        self.end_headers()
        
        print(f"WebSocket client connected: {self.client_address}")
        
        # 启动 WebSocket 代理
        proxy = WebSocketProxy(self.request, GATEWAY_WS)
        proxy.run()
    
    def proxy_request(self):
        """代理请求到 Gateway"""
        target_url = GATEWAY + self.path
        
        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        
        # 构建代理请求
        headers = {}
        if 'Content-Type' in self.headers:
            headers['Content-Type'] = self.headers['Content-Type']
        if 'Authorization' in self.headers:
            headers['Authorization'] = self.headers['Authorization']
        
        req = urllib.request.Request(target_url, data=body, headers=headers, method=self.command)
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                # 检查是否是流式响应
                is_stream = self.path == '/v1/chat/completions' and body and b'"stream":true' in body
                
                if is_stream:
                    # 流式转发
                    self.send_response(response.status)
                    self.send_cors_headers()
                    # SSE 必需的头
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    
                    # 逐块转发
                    while True:
                        chunk = response.read(4096)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        except:
                            # 客户端断开连接
                            break
                else:
                    # 非流式，一次性转发
                    self.send_response(response.status)
                    self.send_cors_headers()
                    # 复制响应头
                    for key, value in response.getheaders():
                        if key.lower() not in ('transfer-encoding',):
                            self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(response.read())
                    
        except urllib.error.URLError as e:
            self.send_response(502)
            self.send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"error": "Gateway error: {e.reason}"}}'.encode())
        except Exception as e:
            self.send_response(500)
            self.send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"error": "{str(e)}"}}'.encode())
    
    def send_cors_headers(self):
        """发送 CORS 头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def log_message(self, format, *args):
        """简化日志"""
        print(f"[{self.command}] {self.path}")


if __name__ == '__main__':
    with http.server.HTTPServer(('0.0.0.0', PORT), ProxyHandler) as httpd:
        print(f"OpenClaw Kindle Panel Server (Python)")
        print(f"面板地址: http://<你的IP>:{PORT}")
        print(f"Gateway 代理: {GATEWAY}")
        print(f"WebSocket 代理: ws://<你的IP>:{PORT}/ws -> {GATEWAY_WS}")
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
