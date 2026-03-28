# 访谈视频智能处理系统 — 项目文档

## 文档目录

| 文档 | 说明 | 状态 |
|------|------|------|
| [开发状态追踪](./DEVELOPMENT_STATUS.md) | 里程碑、已完成/未完成功能 | ✅ 最新 |
| [技术栈与框架](./TECHNICAL_STACK.md) | 技术选型、依赖版本、模型列表 | ✅ 最新 |
| [项目架构](./ARCHITECTURE.md) | 目录结构、模块关系 | ✅ 最新 |
| [API文档](./API.md) | 端点列表、请求/响应格式 | ✅ 最新 |
| [可行性分析报告](./feasibility-report.md) | 技术可行性、模型选型 | 基础文档 |
| [需求规格说明书](./requirements-spec.md) | 功能需求、非功能需求 | 基础文档 |
| [技术方案设计](./technical-design.md) | 架构设计、数据模型 | 基础文档 |
| [开发计划](./development-plan.md) | 里程碑、详细任务 | 基础文档 |

---

## 快速导航

### 已完成模块
- ✅ 后端API框架 (FastAPI)
- ✅ STT推理引擎 (faster-whisper)
- ✅ 说话人分离引擎 (pyannote.audio)
- ✅ 音频处理服务 (FFmpeg/Demucs)
- ✅ 访谈处理管线
- ✅ 前端界面 (React + Ant Design)

### 待完成模块
- ⏳ 面部分析 (MediaPipe)
- ⏳ 声音情绪识别 (emotion2vec+)
- ⏳ 韵律分析
- ⏳ 音频可视化
- ⏳ 情绪融合
- ⏳ 视频关键帧

---

## 快速启动

```bash
# 1. 激活环境
source .venv/bin/activate

# 2. 启动后端
PYTHONPATH=. uvicorn src.api.main:app --reload --port 8000

# 3. 启动前端 (新终端)
cd frontend && npm run dev

# 4. 访问
# 后端: http://localhost:8000/docs
# 前端: http://localhost:3000
```

---

**文档版本**: v0.2  
**更新日期**: 2026-03-21  
**状态**: 开发中
