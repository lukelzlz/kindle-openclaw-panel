#!/usr/bin/env python3
"""
OpenClaw Kindle Panel Server - CORS 代理
用法: python3 server.py [port] [gateway_url]
默认: port=8080, gateway_url=http://127.0.0.1:7860
"""

import http.server
import urllib.request
import urllib.error
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
GATEWAY = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:7860"

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        if self.path.startswith('/v1/') or self.path.startswith('/tools/'):
            self.proxy_request()
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path.startswith('/v1/') or self.path.startswith('/tools/'):
            self.proxy_request()
        else:
            self.send_error(404)
    
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
            with urllib.request.urlopen(req, timeout=60) as response:
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
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
