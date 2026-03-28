# 技术栈与框架

> **更新时间**: 2026-03-21

---

## 核心依赖

### Python 环境

```toml
# pyproject.toml
python = "^3.9"
```

### 后端依赖

| 包 | 版本 | 用途 |
|---|------|------|
| fastapi | ^0.109.0 | Web框架 |
| uvicorn | ^0.27.0 | ASGI服务器 |
| pydantic | ^2.5.0 | 数据验证 |
| sqlalchemy | ^2.0.25 | ORM |
| alembic | ^1.13.0 | 数据库迁移 |

### AI/ML 依赖

| 包 | 版本 | 用途 |
|---|------|------|
| torch | **2.4.0** | 深度学习框架 |
| torchaudio | **2.4.0** | 音频处理 |
| faster-whisper | ^1.0.0 | 语音转文字 |
| pyannote-audio | **3.1.0** | 说话人分离 |
| demucs | ^4.0.0 | 音频降噪 |
| transformers | ^4.36.0 | 模型加载 |
| accelerate | ^0.25.0 | 推理加速 |

### 音视频处理

| 包 | 版本 | 用途 |
|---|------|------|
| librosa | ^0.10.1 | 音频分析 |
| soundfile | ^0.12.1 | 音频读写 |
| scipy | ^1.11.0 | 信号处理 |
| opencv-python | **4.9.0.80** | 视频处理 |
| av | ^12.0.0 | 视频编解码 |
| scenedetect | ^0.6.2 | 场景检测 |
| mediapipe | ^0.10.x | 面部分析 |

### 前端依赖

```json
// frontend/package.json
{
  "react": "^18.3.1",
  "react-router-dom": "^7.1.1",
  "@tanstack/react-query": "^5.62.8",
  "antd": "^5.22.5",
  "recharts": "^2.15.0",
  "axios": "^1.7.9",
  "zustand": "^5.0.2"
}
```

---

## 模型配置

### 已下载模型

| 模型 | 大小 | 位置 |
|------|------|------|
| faster-whisper large-v3-turbo | ~3GB | ~/.cache/huggingface/ |
| pyannote/speaker-diarization-3.1 | ~1GB | ~/.cache/huggingface/ |
| Demucs htdemucs_ft | ~300MB | ~/.cache/torch/hub/ |

### HuggingFace Token

```bash
# 设置环境变量 (从 https://huggingface.co/settings/tokens 获取)
export HF_TOKEN=your_huggingface_token_here
```

**Token来源**: pyannote.audio 需要接受条款:
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

---

## 框架选择理由

### 后端: FastAPI

- 异步支持优秀
- 自动OpenAPI文档
- Pydantic类型安全
- 与SQLAlchemy集成良好

### 前端: React + Ant Design

- 组件丰富 (Table, Form, Tabs等)
- 中文本地化支持
- TypeScript兼容
- 生态成熟

### 数据可视化: Recharts

- React原生
- 响应式设计
- TypeScript支持
- 轻量级

---

## 推理加速

### Apple Silicon (MPS)

```python
# 自动检测
device = "mps" if torch.backends.mps.is_available() else "cpu"

# STT使用
model = WhisperModel("large-v3-turbo", device="mps")

# pyannote使用
pipeline = pipeline.to(torch.device("mps"))
```

### 已知限制

- Demucs 在 MPS 上可能较慢
- 部分模型仅支持 CUDA

---

## 环境变量

```bash
# .env
HF_TOKEN=your_token_here
STT_MODEL=large-v3-turbo
STT_LANGUAGE=zh
```
