// 简单的代理服务器 - 托管 HTML 并代理 Gateway 请求
// 用法: node server.js [port] [gatewayUrl]
// 默认: port=8080, gatewayUrl=http://127.0.0.1:7860

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.argv[2] || process.env.PORT || 8080;
const GATEWAY = process.argv[3] || process.env.GATEWAY_URL || 'http://127.0.0.1:7860';

const server = http.createServer((req, res) => {
    // CORS 头
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    
    if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
    }
    
    // 代理 API 请求到 Gateway
    if (req.url.startsWith('/v1/') || req.url.startsWith('/tools/')) {
        const gatewayUrl = GATEWAY + req.url;
        
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
            const urlObj = new URL(gatewayUrl);
            const options = {
                hostname: urlObj.hostname,
                port: urlObj.port || 80,
                path: urlObj.pathname + urlObj.search,
                method: req.method,
                headers: {
                    'Content-Type': req.headers['content-type'] || 'application/json',
                }
            };
            
            if (req.headers['authorization']) {
                options.headers['Authorization'] = req.headers['authorization'];
            }
            
            const proxyReq = http.request(options, (proxyRes) => {
                // 复制响应头但添加 CORS
                const headers = Object.assign({}, proxyRes.headers);
                headers['Access-Control-Allow-Origin'] = '*';
                res.writeHead(proxyRes.statusCode, headers);
                proxyRes.pipe(res);
            });
            
            proxyReq.on('error', (e) => {
                console.error('Proxy error:', e.message);
                res.writeHead(502, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Gateway error: ' + e.message }));
            });
            
            if (body) proxyReq.write(body);
            proxyReq.end();
        });
        return;
    }
    
    // 托管静态文件
    let filePath = req.url === '/' ? '/index.html' : req.url;
    filePath = path.join(__dirname, filePath);
    
    // 安全检查
    if (!filePath.startsWith(__dirname)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
    }
    
    fs.readFile(filePath, (err, data) => {
        if (err) {
            res.writeHead(404);
            res.end('Not Found');
            return;
        }
        
        // 设置 Content-Type
        const ext = path.extname(filePath);
        const types = {
            '.html': 'text/html',
            '.js': 'application/javascript',
            '.css': 'text/css',
            '.json': 'application/json',
        };
        res.setHeader('Content-Type', types[ext] || 'text/plain');
        res.writeHead(200);
        res.end(data);
    });
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`OpenClaw Kindle Panel Server`);
    console.log(`面板地址: http://<你的IP>:${PORT}`);
    console.log(`Gateway 代理: ${GATEWAY}`);
    console.log(`按 Ctrl+C 停止`);
});
