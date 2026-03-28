# 技术方案设计

> **版本**: v0.1 | **日期**: 2026-03-19 | **状态**: 待审阅

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      表现层 (Web UI)                          │
│   React + Recharts + Ant Design / React-Admin               │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST + WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                      API 层 (FastAPI)                        │
│   /upload  /process  /report  /timeline  /websocket          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    处理引擎层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  视频分析器   │  │  音频分析器   │  │  情绪融合器   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    模型推理层                                 │
│  Ollama / faster-whisper / pyannote / MediaPipe / Demucs    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    数据存储层                                 │
│  SQLite (元数据) / 文件系统 (原始数据/结果)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
interview-ai/
├── src/
│   ├── api/                    # FastAPI 路由
│   │   ├── routes/
│   │   │   ├── interviews.py   # 访谈相关路由
│   │   │   ├── upload.py       # 文件上传
│   │   │   ├── process.py      # 处理任务
│   │   │   └── report.py        # 报告生成
│   │   ├── schemas/            # Pydantic 模型
│   │   └── deps.py             # 依赖注入
│   │
│   ├── core/                   # 核心配置
│   │   ├── config.py           # 配置管理
│   │   ├── security.py         # 安全相关
│   │   └── exceptions.py       # 异常定义
│   │
│   ├── models/                 # 数据模型
│   │   ├── database.py         # SQLAlchemy 模型
│   │   └── enums.py            # 枚举类型
│   │
│   ├── services/               # 业务逻辑
│   │   ├── interview.py        # 访谈管理
│   │   ├── video/              # 视频分析服务
│   │   │   ├── analyzer.py     # 视频分析器
│   │   │   ├── keyframe.py     # 关键帧提取
│   │   │   └── face.py         # 面部分析
│   │   ├── audio/              # 音频处理服务
│   │   │   ├── processor.py    # 音频处理器
│   │   │   ├── denoise.py       # 降噪
│   │   │   ├── transcript.py    # STT转录
│   │   │   ├── diarization.py   # 说话人分离
│   │   │   └── prosody.py       # 韵律分析
│   │   └── emotion/            # 情绪分析服务
│   │       ├── fusion.py        # 多模态融合
│   │       ├── detector.py       # 情绪检测
│   │       └── signals.py       # 信号分析
│   │
│   ├── inference/              # 模型推理
│   │   ├── stt/               # Whisper推理
│   │   ├── diarization/       # pyannote推理
│   │   ├── vad/               # 语音活动检测
│   │   ├── face/              # MediaPipe推理
│   │   └── emotion/           # 情绪识别推理
│   │
│   └── utils/                  # 工具函数
│       ├── video.py            # 视频处理工具
│       ├── audio.py            # 音频处理工具
│       ├── time.py             # 时间处理
│       └── file.py             # 文件操作
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/         # UI组件
│   │   ├── pages/              # 页面
│   │   ├── hooks/              # 自定义Hooks
│   │   ├── services/           # API调用
│   │   └── types/              # TypeScript类型
│   └── public/
│
├── models/                     # 本地模型缓存目录
│
├── tests/                      # 测试
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   └── fixtures/               # 测试数据
│
├── docker/                     # Docker配置
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── docker-compose.yml
│
├── scripts/                    # 运维脚本
│   ├── download_models.py      # 模型下载
│   └── benchmark.py             # 性能基准
│
├── docs/                       # 文档
│
├── pyproject.toml              # Python项目配置
├── package.json                # 前端项目配置
└── README.md
```

---

## 三、核心数据模型

### 3.1 数据库模型

```python
# src/models/database.py

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    duration = Column(Float, nullable=True)        # 秒
    fps = Column(Float, nullable=True)
    resolution = Column(String, nullable=True)     # "1920x1080"
    status = Column(String, default="pending")      # pending/processing/completed/failed
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    speakers = relationship("Speaker", back_populates="interview")
    segments = relationship("AudioSegment", back_populates="interview")
    face_frames = relationship("FaceFrame", back_populates="interview")
    emotion_nodes = relationship("EmotionNode", back_populates="interview")


class Speaker(Base):
    __tablename__ = "speakers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    label = Column(String, nullable=False)         # "访员", "受访者A"
    voice_embedding = Column(JSON, nullable=True)   # 声纹特征
    color = Column(String, nullable=True)          # 可视化颜色
    
    interview = relationship("Interview", back_populates="speakers")
    segments = relationship("AudioSegment", back_populates="speaker")


class AudioSegment(Base):
    __tablename__ = "audio_segments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    speaker_id = Column(String, ForeignKey("speakers.id"), nullable=True)
    
    start_time = Column(Float, nullable=False)     # 秒
    end_time = Column(Float, nullable=False)        # 秒
    transcript = Column(String, nullable=True)     # 转录文本
    confidence = Column(Float, nullable=True)       # 置信度 0-1
    
    # 韵律特征
    prosody = Column(JSON, nullable=True)            # {
                                                     #   "pitch_mean": float,
                                                     #   "pitch_std": float,
                                                     #   "energy_mean": float,
                                                     #   "speech_rate": float,   # 字/分钟
                                                     #   "pause_ratio": float
                                                     # }
    
    # 情绪评分
    emotion_scores = Column(JSON, nullable=True)    # {
                                                     #   "happy": float,
                                                     #   "sad": float,
                                                     #   "angry": float,
                                                     #   "neutral": float,
                                                     #   "anxious": float
                                                     # }
    
    interview = relationship("Interview", back_populates="segments")
    speaker = relationship("Speaker", back_populates="segments")


class FaceFrame(Base):
    __tablename__ = "face_frames"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    
    timestamp = Column(Float, nullable=False)       # 秒
    frame_path = Column(String, nullable=True)       # 关键帧图片路径
    
    face_bbox = Column(JSON, nullable=True)         # [x, y, w, h]
    landmarks = Column(JSON, nullable=True)         # 468个关键点
    
    action_units = Column(JSON, nullable=True)      # {
                                                     #   "AU01": float,  # 眉内角上扬
                                                     #   "AU04": float,  # 眉下垂
                                                     #   "AU12": float,  # 嘴角上扬
                                                     #   "AU17": float,  # 下巴上扬
                                                     #   ...
                                                     # }
    
    emotion_scores = Column(JSON, nullable=True)
    
    interview = relationship("Interview", back_populates="face_frames")


class EmotionNode(Base):
    __tablename__ = "emotion_nodes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String, ForeignKey("interviews.id"), nullable=False)
    
    timestamp = Column(Float, nullable=False)       # 秒
    source = Column(String, nullable=False)          # "audio" | "video" | "fusion"
    label = Column(String, nullable=False)           # "紧张", "回避", "自信"
    intensity = Column(Float, nullable=False)        # 强度 0-1
    confidence = Column(Float, nullable=False)       # 置信度 0-1
    
    # 原始信号来源
    audio_emotion = Column(JSON, nullable=True)      # 音频情绪详情
    video_emotion = Column(JSON, nullable=True)      # 视频情绪详情
    
    interview = relationship("Interview", back_populates="emotion_nodes")
```

### 3.2 API Schema 模型

```python
# src/api/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class InterviewBase(BaseModel):
    filename: str


class InterviewCreate(InterviewBase):
    pass


class InterviewResponse(InterviewBase):
    id: str
    duration: Optional[float] = None
    fps: Optional[float] = None
    resolution: Optional[str] = None
    status: ProcessingStatus
    created_at: datetime
    
    class Config:
        from_attributes = True


class SpeakerResponse(BaseModel):
    id: str
    label: str
    color: Optional[str] = None
    
    class Config:
        from_attributes = True


class SegmentResponse(BaseModel):
    id: str
    speaker_id: Optional[str] = None
    start_time: float
    end_time: float
    transcript: Optional[str] = None
    confidence: Optional[float] = None
    prosody: Optional[Dict] = None
    emotion_scores: Optional[Dict] = None


class FaceFrameResponse(BaseModel):
    id: str
    timestamp: float
    face_bbox: Optional[List[float]] = None
    action_units: Optional[Dict[str, float]] = None
    emotion_scores: Optional[Dict[str, float]] = None


class EmotionNodeResponse(BaseModel):
    id: str
    timestamp: float
    source: str
    label: str
    intensity: float
    confidence: float


class TranscriptResponse(BaseModel):
    interview_id: str
    speakers: List[SpeakerResponse]
    segments: List[SegmentResponse]
    full_text: str


class EmotionAnalysisResponse(BaseModel):
    interview_id: str
    emotion_nodes: List[EmotionNodeResponse]
    summary: Dict  # 情绪统计摘要
    signals: List[Dict]  # 异常信号列表


class TimelineResponse(BaseModel):
    interview_id: str
    duration: float
    speakers: List[SpeakerResponse]
    segments: List[SegmentResponse]
    face_frames: List[FaceFrameResponse]
    emotion_nodes: List[EmotionNodeResponse]


class ReportResponse(BaseModel):
    interview_id: str
    metadata: Dict
    transcript: str
    emotion_summary: Dict
    signals: List[Dict]
    key_moments: List[Dict]
    json_export: str  # 完整JSON的base64或URL
```

---

## 四、API 设计

### 4.1 RESTful API

| 方法 | 路径 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/interviews` | 上传视频，创建访谈 | multipart/form | InterviewResponse |
| GET | `/api/interviews` | 列出所有访谈 | - | List[InterviewResponse] |
| GET | `/api/interviews/{id}` | 获取访谈详情 | - | InterviewResponse |
| DELETE | `/api/interviews/{id}` | 删除访谈 | - | 204 No Content |
| POST | `/api/interviews/{id}/process` | 启动处理任务 | ProcessConfig | TaskResponse |
| GET | `/api/interviews/{id}/status` | 获取处理进度 | - | StatusResponse |
| GET | `/api/interviews/{id}/transcript` | 获取转录结果 | - | TranscriptResponse |
| GET | `/api/interviews/{id}/emotion` | 获取情绪分析 | - | EmotionAnalysisResponse |
| GET | `/api/interviews/{id}/timeline` | 获取时间线数据 | - | TimelineResponse |
| GET | `/api/interviews/{id}/report` | 获取完整报告 | - | ReportResponse |
| GET | `/api/interviews/{id}/frames/{timestamp}` | 获取指定帧 | - | FrameResponse |
| POST | `/api/models/download` | 预下载模型 | ModelDownloadRequest | TaskResponse |
| GET | `/api/models` | 列出可用模型 | - | List[ModelInfo] |

### 4.2 WebSocket API

| 路径 | 功能 | 消息类型 |
|------|------|---------|
| `/ws/interviews/{id}/progress` | 实时处理进度 | ProgressMessage |
| `/ws/interviews/{id}/logs` | 实时日志 | LogMessage |

**ProgressMessage 格式**:
```json
{
  "type": "progress",
  "stage": "transcription",
  "progress": 0.65,
  "message": "正在转录音频...",
  "timestamp": "2026-03-19T10:30:00Z"
}
```

### 4.3 处理配置

```python
class ProcessConfig(BaseModel):
    video_analysis: bool = True           # 启用视频分析
    face_analysis: bool = True           # 启用面部分析
    micro_expression: bool = False        # 启用微表情检测 (P2)
    audio_denoise: bool = True           # 启用降噪
    speaker_diarization: bool = True      # 启用说话人分离
    speech_to_text: bool = True          # 启用STT
    prosody_analysis: bool = True        # 启用韵律分析
    emotion_recognition: bool = True     # 启用情绪识别
    multimodal_fusion: bool = True       # 启用多模态融合
    
    # 模型选择
    stt_model: str = "large-v3-turbo"    # faster-whisper模型
    diarization_model: str = "pyannote-3.1"
    
    # 处理参数
    keyframe_interval: float = 5.0       # 关键帧间隔(秒)
    face_sample_rate: float = 2.0        # 面部分析帧率
```

---

## 五、处理流程

### 5.1 整体流程

```
视频上传
    │
    ▼
[1] 预处理
    ├─ 视频解码 + 参数检测
    ├─ 计算总帧数、时长
    └─ 创建数据库记录
    │
    ▼
[2] 场景检测 / 关键帧提取
    │  PySceneDetect
    │  提取场景边界和关键帧列表
    ▼
[3] 并行处理分支
    │
    ├──────────────────────────────────────┐
    ▼                                      ▼
[3a] 音频处理管线                   [3b] 视频处理管线
    │                                      │
    ▼                                      ▼
    ├─ 音频提取 (FFmpeg)              ├─ 人物检测 (YOLOv8)
    │                                      │  ├─ 关键帧处理
    ├─ 降噪 (Demucs)                  │  ├─ 人脸检测
    │                                      │  ├─ 追踪
    ├─ 人声分离 (Demucs)              │
    │                                      ├─ 面部分析 (MediaPipe)
    ├─ VAD (语音活动检测)             │  ├─ 468关键点提取
    │                                      │  ├─ AU计算
    ├─ 说话人分离 (pyannote)          │
    │                                      ├─ 情绪分类 (LSTM)
    ├─ STT转录 (Whisper)               │
    │                                      └─ 微表情检测 (P2)
    ├─ 时间戳对齐 (WhisperX)
    │                                     
    ├─ 韵律分析 (praat)               
    │  ├─ 基频F0                      
    │  ├─ 能量                       
    │  ├─ 语速                       
    │  └─ 停顿                       
    │                                     
    └─ 声音情绪 (emotion2vec+)         
    │
    ▼
[4] 信号检测
    ├─ 压力信号 (语速异常、F0抖动)
    ├─ 回避信号 (填充词、停顿)
    ├─ 情绪波动 (能量突变)
    └─ 自信度评估
    │
    ▼
[5] 多模态情绪融合
    ├─ 时间线对齐
    ├─ 跨模态情绪融合
    └─ 综合情绪节点生成
    │
    ▼
[6] 报告生成
    ├─ 结构化JSON
    ├─ Markdown摘要
    └─ 可疑信号标记
    │
    ▼
[7] 结果存储
    ├─ 数据库更新
    └─ 文件系统（关键帧、报告）
```

### 5.2 分段处理策略

对于长视频（>30分钟），采用分段处理：

```python
def process_video分段策略(video_path: str, max_duration: int = 1800):
    """
    max_duration: 每段最大时长(秒)，默认30分钟
    """
    total_duration = get_video_duration(video_path)
    
    if total_duration <= max_duration:
        # 短视频：直接处理
        return process_video_direct(video_path)
    else:
        # 长视频：分段处理
        segments = []
        for start in range(0, total_duration, max_duration - 60):  # 60秒重叠
            end = min(start + max_duration, total_duration)
            
            # 提取片段
            segment_path = extract_segment(video_path, start, end)
            
            # 处理片段
            result = process_video_direct(segment_path)
            
            # 偏移时间戳
            result = adjust_timestamps(result, start)
            segments.append(result)
        
        # 合并结果
        return merge_results(segments)
```

---

## 六、情绪分析算法

### 6.1 声音情绪分析

```python
# 情绪分类 (基于emotion2vec+)
emotion_labels = ["happy", "sad", "angry", "fear", "neutral", "surprise", "disgust"]

def analyze_voice_emotion(audio_segment: np.ndarray, sr: int) -> Dict[str, float]:
    """分析声音情绪"""
    # 1. 提取情绪embedding
    emotion_embedding = emotion2vec_inference(audio_segment, sr)
    
    # 2. 分类
    scores = emotion_classifier(emotion_embedding)
    
    return {label: float(score) for label, score in zip(emotion_labels, scores)}


# 心理信号检测
def detect_psychological_signals(segment: AudioSegment) -> List[Signal]:
    """检测心理信号"""
    signals = []
    prosody = segment.prosody
    
    # 压力信号：语速异常、F0抖动
    if prosody.speech_rate > 250:  # 字/分钟，高于正常值
        signals.append(Signal(type="stress", intensity=0.8, indicator="语速过快"))
    if prosody.pitch_std > 50:    # F0标准差过大
        signals.append(Signal(type="stress", intensity=0.7, indicator="音调波动大"))
    
    # 回避信号：填充词、异常停顿
    if segment.transcript and count_filler_words(segment.transcript) > 3:
        signals.append(Signal(type="avoidance", intensity=0.6, indicator="填充词过多"))
    if prosody.pause_ratio > 0.3:
        signals.append(Signal(type="avoidance", intensity=0.5, indicator="停顿频繁"))
    
    # 情绪波动
    if prosody.energy_std > 0.5:  # 能量变化剧烈
        signals.append(Signal(type="emotion_fluctuation", intensity=0.7, indicator="情绪波动"))
    
    return signals
```

### 6.2 面部动作单元 (AU) 分析

```python
# 基于MediaPipe的AU计算
AU_DEFINITIONS = {
    "AU01": "眉内角上扬",      # Inner brow raiser
    "AU02": "眉外角上扬",      # Outer brow raiser
    "AU04": "眉下垂",          # Brow lowerer
    "AU05": "眼睑上扬",        # Upper lid raiser
    "AU06": "脸颊上扬",        # Cheek raiser
    "AU09": "鼻子上皱",        # Nose wrinkler
    "AU12": "嘴角上扬",        # Lip corner puller
    "AU15": "嘴角下压",        # Lip corner depressor
    "AU17": "下巴上扬",        # Chin raiser
    "AU20": "嘴唇拉伸",        # Lip stretcher
    "AU25": "嘴唇分开",        # Lips part
    "AU26": "下颌下垂",        # Jaw drop
}

def compute_action_units(landmarks: List[Point], prev_landmarks: List[Point] = None) -> Dict[str, float]:
    """计算动作单元强度"""
    aus = {}
    
    # 使用关键点计算AU强度
    # 这里需要根据FACS标准实现具体算法
    
    # AU01 + AU02: 眉毛上扬
    brow_height = compute_brow_height(landmarks)
    aus["AU01"] = clamp(brow_height / brow_height_baseline, 0, 1)
    aus["AU02"] = clamp((brow_height - aus["AU01"]) * 1.2, 0, 1)
    
    # AU12: 嘴角上扬 (微笑)
    mouth_corner_diff = compute_mouth_corner_asymmetry(landmarks)
    aus["AU12"] = clamp(mouth_corner_diff * 2.0, 0, 1)
    
    # 更多AU计算...
    
    return aus


def detect_micro_expression(au_sequence: List[Dict[str, float]], fps: float) -> List[MicroExpression]:
    """
    检测微表情
    基于AU强度时序变化，检测快速(100-500ms)的表情变化
    """
    micro_expressions = []
    
    # 1. 滑动窗口检测AU突变
    window_size = int(0.5 * fps)  # 500ms窗口
    
    for i in range(len(au_sequence) - window_size):
        window = au_sequence[i:i + window_size]
        
        # 2. 检测AU强度快速变化
        for au_name in au_sequence[0].keys():
            au_values = [frame.get(au_name, 0) for frame in window]
            
            # 计算变化率
            change_rate = (max(au_values) - min(au_values)) / 0.5  # 500ms内的变化
            
            if change_rate > THRESHOLD:  # 阈值需要校准
                micro_expressions.append(MicroExpression(
                    start_time=i / fps,
                    duration=0.5,
                    au_name=au_name,
                    intensity=change_rate,
                    type=infer_emotion_from_au(au_name)
                ))
    
    return micro_expressions
```

### 6.3 多模态情绪融合

```python
def fuse_multimodal_emotion(
    audio_emotion: Dict[str, float],
    video_emotion: Dict[str, float],
    prosody: ProsodyFeatures,
    au_intensity: Dict[str, float]
) -> Dict[str, float]:
    """多模态情绪融合"""
    
    # 1. 归一化权重 (可根据场景调整)
    weights = {
        "audio": 0.4,
        "video": 0.4,
        "prosody": 0.2
    }
    
    # 2. 简单加权融合
    fused = {}
    for emotion in EMOTION_LABELS:
        score = (
            weights["audio"] * audio_emotion.get(emotion, 0) +
            weights["video"] * video_emotion.get(emotion, 0) +
            weights["prosody"] * prosody_to_emotion_score(prosody, emotion)
        )
        fused[emotion] = clamp(score, 0, 1)
    
    return fused


def generate_emotion_nodes(
    fused_emotions: List[Dict[str, float]],
    timestamps: List[float],
    signals: List[Signal]
) -> List[EmotionNode]:
    """生成情绪节点"""
    nodes = []
    
    # 1. 基于情绪变化生成节点
    for i in range(1, len(fused_emotions)):
        prev, curr = fused_emotions[i-1], fused_emotions[i]
        
        # 计算变化
        change = sum(abs(curr[e] - prev[e]) for e in EMOTION_LABELS)
        
        if change > EMOTION_CHANGE_THRESHOLD:
            # 情绪显著变化
            dominant = max(curr, key=curr.get)
            nodes.append(EmotionNode(
                timestamp=timestamps[i],
                source="fusion",
                label=dominant,
                intensity=curr[dominant],
                confidence=compute_confidence(curr)
            ))
    
    # 2. 合并信号检测结果
    for signal in signals:
        nodes.append(EmotionNode(
            timestamp=signal.timestamp,
            source="signal",
            label=signal.type,
            intensity=signal.intensity,
            confidence=signal.confidence
        ))
    
    # 3. 按时间排序
    nodes.sort(key=lambda n: n.timestamp)
    
    return nodes
```

---

## 七、模型推理抽象

```python
# src/inference/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import numpy as np


class InferenceEngine(ABC):
    """推理引擎抽象基类"""
    
    def __init__(self, model_path: str, device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self.model = None
    
    @abstractmethod
    def load(self):
        """加载模型"""
        pass
    
    @abstractmethod
    def unload(self):
        """卸载模型"""
        pass
    
    @abstractmethod
    def infer(self, input_data: Any) -> Any:
        """推理"""
        pass


class STTEngine(InferenceEngine):
    """语音转文字引擎"""
    
    def __init__(self, model_name: str = "large-v3-turbo", **kwargs):
        super().__init__(model_name, **kwargs)
        self.model = None
        self.task = None
    
    def load(self):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(
            self.model_path or self.model_name,
            device="cuda" if self.device == "cuda" else "cpu",
            compute_type="float16" if self.device == "cuda" else "int8"
        )
    
    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "zh",
        vad_filter: bool = True
    ) -> Dict:
        """转录"""
        segments, info = self.model.transcribe(
            audio,
            language=language,
            vad_filter=vad_filter,
            word_timestamps=True
        )
        
        return {
            "text": "".join([s.text for s in segments]),
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "words": [
                        {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                        for w in (s.words or [])
                    ]
                }
                for s in segments
            ],
            "language": info.language
        }


class DiarizationEngine(InferenceEngine):
    """说话人分离引擎"""
    
    def __init__(self, model_name: str = "pyannote-3.1", **kwargs):
        super().__init__(model_name, **kwargs)
    
    def load(self):
        from pyannote.audio import Pipeline
        self.model = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=self.hf_token
        )
    
    def diarize(self, audio_path: str) -> List[Dict]:
        """说话人分离"""
        diarization = self.model(audio_path)
        
        return [
            {
                "start": turn.start,
                "end": turn.end,
                "speaker": f"SPEAKER_{segment.label}"
            }
            for segment, _, turn in diarization.itertracks(yield_label=True)
        ]
```

---

## 八、技术栈总结

| 层次 | 技术选型 | 理由 |
|------|---------|------|
| **后端框架** | FastAPI | 异步支持好，类型安全，自动文档 |
| **数据库** | SQLite (开发) / PostgreSQL (生产) | 轻量/成熟 |
| **ORM** | SQLAlchemy + Alembic | 成熟稳定 |
| **任务队列** | Celery + Redis | 分布式任务处理 |
| **STT** | faster-whisper | C++高速推理 |
| **说话人分离** | pyannote.audio 3.1 | 开源SOTA |
| **降噪** | Demucs | 深度学习降噪 |
| **面部分析** | MediaPipe | 成熟稳定 |
| **声音情绪** | emotion2vec+ | 多分类支持 |
| **韵律分析** | praat-parselmouth | 标准工具 |
| **前端框架** | React + TypeScript | 生态丰富 |
| **可视化** | Recharts + D3.js | 灵活图表 |
| **UI组件** | Ant Design / Chakra UI | 快速开发 |
| **推理服务** | Ollama (开发) / vLLM (生产) | 本地模型管理 |
| **容器化** | Docker + Docker Compose | 环境一致性 |
