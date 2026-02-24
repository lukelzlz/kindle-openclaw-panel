# Kindle Panel - OpenClaw 聊天面板

适用于 Kindle 浏览器的 OpenClaw 聊天界面，支持 E-ink 屏幕优化显示。

## 功能特性

- ✅ **WebSocket 连接** - 使用 Gateway WebSocket API 进行实时通信
- ✅ **流式响应** - 实时显示 AI 回复（通过 WebSocket chat 事件）
- ✅ **E-ink 优化** - 高对比度黑白界面，适配 Kindle 浏览器
- ✅ **自动重连** - WebSocket 断开时自动尝试重新连接
- ✅ **Markdown 渲染** - 支持代码块、粗体、斜体、链接、列表、引用
- ✅ **历史记录** - LocalStorage 本地存储 + 服务端历史同步
- ✅ **连接状态指示** - 实时显示 WebSocket 连接状态
- ✅ **WebSocket 代理** - Python 代理支持旧浏览器（/ws 端点）

## 部署步骤

### 1. 启动 Gateway

确保 Gateway 服务已启动（默认端口 7860）：

```bash
openclaw gateway status
# 如果未启动:
openclaw gateway start
```

### 2. 启动 Python 代理服务器（可选）

如果浏览器支持直接 WebSocket 连接，可以直接打开 index.html。
如果需要代理（如跨域问题或旧浏览器），启动服务器：

```bash
cd kindle-panel
python3 server.py
```

服务器会在 `http://0.0.0.0:8080` 启动。

### 3. 访问面板

**方式一：直接访问（浏览器支持 WebSocket）**

直接在浏览器中打开 index.html 文件，配置 Gateway WebSocket 地址。

**方式二：通过代理访问**

在浏览器中访问：
```
http://<你的电脑IP>:8080
```

**方式三：Kindle 设备**

在 Kindle 浏览器中访问：
```
http://<你的电脑IP>:8080
```

## 配置说明

### 配置面板（点击 "⚙️ 配置" 展开）

| 选项 | 说明 | 默认值 |
|------|------|--------|
| **Gateway WebSocket 地址** | Gateway WebSocket 地址 | ws://127.0.0.1:7860 |
| **Gateway Token** | 认证 Token，如设置了 gateway.auth.token 则填写 | 空 |
| **Session Key** | OpenClaw session key | main |
| **Agent ID** | OpenClaw agent id（用于历史同步） | main |
| **自动重连** | WebSocket 断开时自动尝试重新连接 | ✅ 启用 |

## WebSocket 协议

### 连接流程

1. 连接 WebSocket（默认 ws://127.0.0.1:7860）
2. 发送 `connect` 请求：

```json
{
  "type": "req",
  "id": "c1",
  "method": "connect",
  "params": {
    "minProtocol": 3,
    "maxProtocol": 3,
    "client": {
      "id": "kindle-panel",
      "displayName": "Kindle Panel",
      "version": "1.0.0",
      "platform": "kindle",
      "mode": "ui"
    }
  }
}
```

3. 等待 `hello-ok` 响应

### 发送消息 (chat.send)

```json
{
  "type": "req",
  "id": "r1",
  "method": "chat.send",
  "params": {
    "sessionKey": "main",
    "text": "用户消息内容",
    "idempotencyKey": "uuid-v4"
  }
}
```

### 接收响应

订阅 `chat` 事件，服务端会推送：

```json
{
  "type": "event",
  "event": "chat",
  "payload": {
    "delta": {"text": "部分响应文本"},
    "runId": "xxx",
    "done": false
  }
}
```

## WebSocket 代理模式

如果浏览器不支持直接 WebSocket 连接（如跨域限制），可以通过 Python 代理：

1. 前端连接 `ws://proxy-host:8080/ws`
2. 代理将 WebSocket 流量转发到 Gateway
3. 代理处理握手和帧转发

## 常见问题

### Q: 显示"浏览器不支持 WebSocket"？

A: Kindle 浏览器较老，可能不支持 WebSocket。此时可以通过 Python 代理服务器访问（代理会处理 WebSocket 转换）。

### Q: 连接后立即断开？

A: 检查 Gateway 是否正常运行，以及 WebSocket 地址是否正确。

### Q: 如何从服务端加载历史？

A: 点击配置中的"从服务端加载历史"按钮，会通过 HTTP API 获取历史消息。

### Q: 如何清除聊天记录？

A: 点击底部"清除历史"按钮，确认后清空 LocalStorage 和界面显示。

## 文件结构

```
kindle-panel/
├── server.py       # Python 代理服务器（HTTP + WebSocket）
├── index.html      # 前端界面（WebSocket 版本）
└── README.md       # 本文档
```

## 技术栈

- **后端**: Python 3 + http.server + urllib
- **前端**: 纯 HTML/CSS/JavaScript（无框架）
- **通信**: WebSocket (Gateway 协议)
- **渲染**: 自定义 Markdown 解析器

## 开发笔记

- Kindle 浏览器基于老版本 WebKit，不完全支持 ES6+
- 使用 `var` 而非 `let`/`const` 以提高兼容性
- 避免使用箭头函数，使用传统 `function` 声明
- CSS 使用 `-webkit-appearance: none` 移除默认样式
- WebSocket 连接支持自动重连

## 从 HTTP API 迁移

旧版本使用 `/v1/chat/completions` HTTP API，新版本使用 Gateway WebSocket API：

| 功能 | 旧版 (HTTP) | 新版 (WebSocket) |
|------|-------------|------------------|
| 连接 | HTTP 请求 | WebSocket 长连接 |
| 发送消息 | POST /v1/chat/completions | chat.send method |
| 接收响应 | SSE 流式 | chat event |
| 历史记录 | 本地存储 + /tools/invoke | 本地存储 + chat.history |
| 状态 | 无状态 | 有状态（session） |

## License

MIT
