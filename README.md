# Kindle Panel - OpenClaw 聊天面板

适用于 Kindle 浏览器的 OpenClaw 聊天界面，支持 E-ink 屏幕优化显示。

## 功能特性

- ✅ **E-ink 优化** - 高对比度黑白界面，适配 Kindle 浏览器
- ✅ **流式传输** - 实时显示 AI 回复（自动检测浏览器支持）
- ✅ **智能降级** - 不支持流式时自动切换普通模式（Kindle 兼容）
- ✅ **Markdown 渲染** - 支持代码块、粗体、斜体、链接、列表、引用
- ✅ **500 错误重试** - 服务器错误自动重试 2 次 + 手动重试按钮
- ✅ **系统代理支持** - 后端自动读取系统代理配置
- ✅ **历史记录** - LocalStorage 本地存储聊天记录
- ✅ **服务端同步** - 可从 OpenClaw session 同步历史消息

## 部署步骤

### 1. 启用 OpenClaw Chat Completions API

在 `~/.openclaw/config` 中添加：

```json
{
  "gateway": {
    "http": {
      "endpoints": {
        "chatCompletions": { "enabled": true }
      }
    }
  }
}
```

或运行命令：

```bash
openclaw config patch '{"gateway":{"http":{"endpoints":{"chatCompletions":{"enabled":true}}}}}'
```

### 2. 启动 Python 代理服务器

```bash
cd kindle-panel
python3 server.py
```

服务器会在 `http://0.0.0.0:8888` 启动，自动使用系统代理。

### 3. 在 Kindle 上访问

在 Kindle 浏览器中访问：

```
http://<你的电脑IP>:8888
```

## 配置说明

### 配置面板（点击 "⚙️ 配置" 展开）

| 选项 | 说明 | 默认值 |
|------|------|--------|
| **Gateway HTTP 地址** | OpenClaw Gateway 地址，留空使用代理模式 | 空（通过代理访问） |
| **Gateway Token** | 认证 Token，如设置了 gateway.auth.token 则填写 | 空 |
| **Agent ID** | OpenClaw agent id | main |
| **同步 Session Key** | 从服务端同步历史的 session key | 空 |
| **允许流式传输回退** | 浏览器不支持流式时自动降级到普通模式 | ✅ 启用 |

### 流式传输说明

- **自动检测**：代码会检测浏览器是否支持 `ReadableStream` API
- **智能降级**：如果不支持但启用了"允许回退"，自动切换到普通请求模式
- **Kindle 兼容**：Kindle 浏览器较老，建议保持"允许回退"开启

## 常见问题

### Q: 500 错误怎么办？

A: 系统会自动重试 2 次，如果仍失败会显示"重试"按钮，点击即可手动重试。

### Q: Kindle 上看不到流式效果？

A: 正常现象，Kindle 浏览器不支持现代流式 API，但"允许回退"选项确保了普通模式可用。

### Q: 如何清除聊天记录？

A: 点击底部"清除历史"按钮，确认后清空 LocalStorage 和界面显示。

### Q: 系统代理怎么配置？

A: 后端 Python 服务器使用 `urllib.request.getproxies()` 自动读取系统代理配置：
- **macOS**: 系统偏好设置 → 网络 → 高级 → 代理
- **Linux**: 环境变量 `http_proxy`, `https_proxy`
- **Windows**: 设置 → 网络 → 代理

## 文件结构

```
kindle-panel/
├── server.py       # Python 代理服务器（支持系统代理）
├── index.html      # 前端界面
└── README.md       # 本文档
```

## 技术栈

- **后端**: Python 3 + http.server + urllib
- **前端**: 纯 HTML/CSS/JavaScript（无框架）
- **渲染**: 自定义 Markdown 解析器
- **传输**: SSE (Server-Sent Events) / XHR 降级

## 开发笔记

- Kindle 浏览器基于老版本 WebKit，不完全支持 ES6+
- 使用 `var` 而非 `let`/`const` 以提高兼容性
- 避免使用箭头函数，使用传统 `function` 声明
- CSS 使用 `-webkit-appearance: none` 移除默认样式

## License

MIT
