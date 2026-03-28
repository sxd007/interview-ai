# 开发状态追踪

> **更新时间**: 2026-03-21

---

## 里程碑

| 阶段 | 状态 | 完成日期 | 备注 |
|------|------|---------|------|
| Phase 0: 项目骨架 | ✅ 完成 | 2026-03-19 | 目录结构、FastAPI框架、数据库模型 |
| Phase 1: 核心音频处理 | ✅ 完成 | 2026-03-21 | STT、说话人分离、降噪 |
| Phase 2: 前端界面 | ✅ 完成 | 2026-03-21 | React + Ant Design |
| Phase 3: 面部分析 | ✅ 完成 | 2026-03-21 | MediaPipe Face Mesh, AU计算 |
| Phase 4: 情绪与韵律 | ✅ 完成 | 2026-03-21 | emotion2vec+, 韵律分析 |
| Phase 5: 可视化与融合 | ✅ 完成 | 2026-03-21 | Recharts图表、情绪融合 |
| Phase 6: 关键帧提取 | ✅ 完成 | 2026-03-21 | PySceneDetect场景检测 |
| Phase 7: PDF报告 | ✅ 完成 | 2026-03-21 | ReportLab中文报告 |
| Phase 8: STT引擎切换 | ✅ 完成 | 2026-03-21 | Faster-Whisper/SenseVoice |
| Phase 9: 高级功能 | ⏳ 待开发 | - | 微表情检测 |

---

## 已完成功能

### 后端 (src/)

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **STT引擎** | `inference/stt/engine.py` | ✅ | faster-whisper封装，支持引擎切换 |
| **SenseVoice引擎** | `inference/stt/sensevoice.py` | ✅ | FunAudioLLM SenseVoice (中文优化) |
| **说话人分离** | `inference/diarization/engine.py` | ✅ | pyannote封装 |
| **音频处理** | `services/audio/processor.py` | ✅ | FFmpeg提取、降噪 |
| **韵律分析** | `services/audio/prosody.py` | ✅ | F0/能量/语速/停顿/填充词 |
| **声音情绪** | `inference/emotion/engine.py` | ✅ | emotion2vec+ (fallback降级) |
| **面部分析** | `inference/face/engine.py` | ✅ | MediaPipe Face Mesh, 468关键点 |
| **AU计算** | `inference/face/engine.py` | ✅ | 12+动作单元强度计算 |
| **视频关键帧** | `services/video/keyframe.py` | ✅ | PySceneDetect场景检测 |
| **PDF报告生成** | `services/report/generator.py` | ✅ | ReportLab中文报告 |
| **访谈处理** | `services/interview.py` | ✅ | 整合完整管线 |
| **API路由** | `api/routes/*.py` | ✅ | 上传、列表、转录、情绪、时间线、报告、关键帧、PDF下载 |

### 前端 (frontend/src/)

| 页面 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 首页 | `pages/HomePage.tsx` | ✅ | 功能概览 |
| 上传页 | `pages/UploadPage.tsx` | ✅ | 拖拽上传、自动处理 |
| 列表页 | `pages/InterviewListPage.tsx` | ✅ | 搜索、状态管理 |
| 详情页 | `pages/InterviewDetailPage.tsx` | ✅ | 转录、时间线、说话人、韵律、情绪 |
| 韵律图表 | `components/ProsodyChart.tsx` | ✅ | 音高/能量/语速可视化 |
| 情绪图表 | `components/EmotionChart.tsx` | ✅ | 情绪分布饼图、信号列表 |

### 模型

| 模型 | 状态 | 用途 |
|------|------|------|
| faster-whisper | ✅ 已下载 | 语音转文字 |
| Demucs htdemucs_ft | ✅ 已下载 | 音频降噪 |
| pyannote.audio 3.1 | ✅ 已下载 | 说话人分离 |
| MediaPipe | ✅ 已安装 | 面部分析 |
| emotion2vec+ | ✅ 已集成 | 声音情绪识别 |
| SenseVoice | ✅ 已集成 | 中文优化STT（可选引擎）|
| funasr | ✅ 已安装 | SenseVoice依赖 |

---

## 待开发功能

### 优先级 P1 (高级)

| 功能 | 说明 |
|------|------|
| 微表情检测 | CNN/LSTM时序分析 |

---

## 已修复的问题

1. **PyTorch 2.8兼容性** → 降级到 2.4.0 (pyannote需求)
2. **NumPy 2.0兼容性** → 锁定 `<2.0` (pyannote需求)
3. **OpenCV版本** → 锁定 `4.9.0.80`
4. **Python 3.9类型注解** → 使用 `Optional[]` 而非 `|`

---

## 硬件环境

```
设备: Mac mini M4
内存: 24GB
加速: MPS (Metal Performance Shaders)
Python: 3.9.6
```
