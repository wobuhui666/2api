# Vertex AI Anonymous to Gemini API

将 Vertex AI Anonymous 的图片生成功能封装为标准的 Google Gemini API 格式的 HTTP 服务。

## 功能特性

- ✅ 兼容 Google Gemini API 格式 (`/v1beta/models/{model}:generateContent`)
- ✅ 支持文生图 (Text-to-Image)
- ✅ 支持图生图 (Image-to-Image)
- ✅ 自动管理 Recaptcha Token（共享 Token，自动刷新）
- ✅ 支持代理配置
- ✅ Docker 部署支持
- ✅ 健康检查端点

## 支持的模型

- `gemini-2.0-flash-preview-image-generation` - Gemini 2.0 图片生成
- `gemini-3-pro-image-preview` - Gemini 3 Pro 图片预览版

## 快速开始

### 使用 Docker Compose（推荐）

1. 克隆仓库：
```bash
git clone <repository-url>
cd 2api
```

2. 复制并修改环境变量配置：
```bash
cp .env.example .env
# 编辑 .env 文件，按需修改配置
```

3. 启动服务：
```bash
docker-compose up -d
```

4. 检查服务状态：
```bash
curl http://localhost:8000/health
```

### 使用 Docker

```bash
# 构建镜像
docker build -t vertex-ai-gemini-api .

# 运行容器
docker run -d \
  --name vertex-ai-gemini-api \
  -p 8000:8000 \
  -e PROXY="http://your-proxy:7890" \
  vertex-ai-gemini-api
```

### 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 复制环境变量配置：
```bash
cp .env.example .env
```

3. 运行服务：
```bash
python -m app.main
```

## API 使用

### 文生图 (Text-to-Image)

```bash
curl -X POST "http://localhost:8000/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "生成一只可爱的橘猫，背景是蓝天白云"
          }
        ]
      }
    ],
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"]
    }
  }'
```

### 图生图 (Image-to-Image)

```bash
curl -X POST "http://localhost:8000/v1beta/models/gemini-3-pro-image-preview:generateContent" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "将这张图片转换为水彩画风格"
          },
          {
            "inlineData": {
              "mimeType": "image/png",
              "data": "BASE64_ENCODED_IMAGE_DATA"
            }
          }
        ]
      }
    ],
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"]
    }
  }'
```

### 响应格式

成功响应：
```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "这是一只可爱的橘猫..."
          },
          {
            "inlineData": {
              "mimeType": "image/png",
              "data": "BASE64_ENCODED_IMAGE_DATA"
            }
          }
        ],
        "role": "model"
      },
      "finishReason": "STOP",
      "index": 0
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 0,
    "candidatesTokenCount": 0,
    "totalTokenCount": 0
  },
  "modelVersion": "gemini-2.0-flash-preview-image-generation"
}
```

错误响应：
```json
{
  "error": {
    "code": 400,
    "message": "Error message",
    "status": "INVALID_ARGUMENT"
  }
}
```

## 配置选项

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `HOST` | 服务监听地址 | `0.0.0.0` |
| `PORT` | 服务监听端口 | `8000` |
| `PROXY` | 代理服务器地址 | `None` |
| `TIMEOUT` | 请求超时时间（秒） | `120` |
| `MAX_RETRY` | 最大重试次数 | `3` |
| `TEXT_RESPONSE` | 是否返回文本 | `true` |
| `SYSTEM_PROMPT` | 系统提示词 | `None` |
| `VERTEX_AI_BASE_API` | Vertex AI API 地址 | `https://content-aiplatform.googleapis.com` |
| `RECAPTCHA_BASE_API` | Recaptcha API 地址 | `https://www.google.com` |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康检查 |
| `/docs` | GET | Swagger API 文档 |
| `/redoc` | GET | ReDoc API 文档 |
| `/v1beta/models` | GET | 列出支持的模型 |
| `/v1beta/models/{model}` | GET | 获取模型信息 |
| `/v1beta/models/{model}:generateContent` | POST | 生成内容 |

## 项目结构

```
2api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py          # 请求模型
│   │   └── response.py         # 响应模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── provider.py         # Vertex AI Anonymous Provider
│   │   ├── recaptcha.py        # Recaptcha 处理
│   │   └── session.py          # HTTP 会话管理
│   └── routers/
│       ├── __init__.py
│       └── generate.py         # 生成内容端点
├── plans/
│   └── architecture.md         # 架构设计文档
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## 注意事项

1. **代理配置**：如果无法直接访问 Google 服务，需要配置 `PROXY` 环境变量
2. **Token 共享**：多个请求共享同一个 Recaptcha Token，Token 失效时会自动刷新
3. **重试机制**：遇到临时错误时会自动重试，最大重试次数由 `MAX_RETRY` 配置
4. **内容过滤**：如果遇到内容审核拦截，不会重试，直接返回错误

## License

MIT License