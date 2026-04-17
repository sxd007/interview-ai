# 处理任务 API

> **基础路径**: `/api/interviews`

---

## 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{interview_id}/process` | 执行完整处理管线 |
| GET | `/{interview_id}/progress` | 获取处理进度 |
| GET | `/{interview_id}/transcript` | 获取转录结果 |
| GET | `/{interview_id}/speakers` | 获取说话人列表 |
| GET | `/{interview_id}/segments` | 获取音频片段 |
| GET | `/{interview_id}/emotion` | 获取情绪分析结果 |
| GET | `/{interview_id}/timeline` | 获取时间线数据 |
| GET | `/{interview_id}/keyframes` | 获取关键帧 |
| GET | `/{interview_id}/faces` | 获取面部帧数据 |
| GET | `/{interview_id}/report` | 获取分析报告 |

---

## 执行处理管线

### POST /api/interviews/{interview_id}/process

启动访谈视频的完整处理管线。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求体** (application/json):
```json
{
  "video_analysis": true,
  "face_analysis": true,
  "micro_expression": false,
  "audio_denoise": true,
  "speaker_diarization": false,
  "speech_to_text": true,
  "prosody_analysis": true,
  "emotion_recognition": true,
  "multimodal_fusion": true,
  "stt_model": "large-v3-turbo",
  "stt_engine": null,
  "diarization_model": "pyannote-3.1",
  "diarization_engine": "pyannote",
  "keyframe_interval": 5.0,
  "face_sample_rate": 2.0,
  "chunk_enabled": false,
  "chunk_duration": 600.0
}
```

**请求参数说明**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `video_analysis` | bool | true | 是否启用视频分析 |
| `face_analysis` | bool | true | 是否启用面部分析 |
| `micro_expression` | bool | false | 是否启用微表情检测 |
| `audio_denoise` | bool | true | 是否启用音频降噪 |
| `speaker_diarization` | bool | false | 是否启用说话人分离 |
| `speech_to_text` | bool | true | 是否启用语音转文字 |
| `prosody_analysis` | bool | true | 是否启用韵律分析 |
| `emotion_recognition` | bool | true | 是否启用情绪识别 |
| `multimodal_fusion` | bool | true | 是否启用多模态融合 |
| `stt_model` | string | "large-v3-turbo" | STT模型大小 |
| `stt_engine` | string | null | STT引擎类型 |
| `diarization_model` | string | "pyannote-3.1" | 说话人分离模型 |
| `diarization_engine` | string | "pyannote" | 说话人分离引擎 |
| `keyframe_interval` | float | 5.0 | 关键帧提取间隔（秒） |
| `face_sample_rate` | float | 2.0 | 面部分析采样率（fps） |
| `chunk_enabled` | bool | false | 是否启用视频分块 |
| `chunk_duration` | float | 600.0 | 分块时长（秒） |

**请求示例**:
```bash
curl -X POST http://localhost:8000/api/interviews/abc123/process \
  -H "Content-Type: application/json" \
  -d '{"video_analysis": true, "face_analysis": true}'
```

**成功响应** (200 OK):
```json
{
  "task_id": "task-abc123",
  "status": "processing",
  "message": "Processing started for interview abc123"
}
```

**错误响应**:

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 404 | `INTERVIEW_NOT_FOUND` | 访谈不存在 |
| 400 | `VALIDATION_ERROR` | 参数验证失败 |
| 503 | `MODEL_LOAD_ERROR` | 模型加载失败 |
| 503 | `GPU_ERROR` | GPU不可用 |

---

## 获取处理进度

### GET /api/interviews/{interview_id}/progress

获取当前处理进度。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/progress
```

**成功响应** (200 OK):
```json
{
  "interview_id": "abc123",
  "status": "processing",
  "progress": 0.65,
  "current_stage": "emotion_analysis",
  "message": "Analyzing emotions from audio segments"
}
```

**响应字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |
| `status` | string | 当前状态 |
| `progress` | float | 进度百分比 (0.0-1.0) |
| `current_stage` | string | 当前处理阶段 |
| `message` | string | 进度消息 |

---

## 获取转录结果

### GET /api/interviews/{interview_id}/transcript

获取语音转文字结果。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/transcript
```

**成功响应** (200 OK):
```json
{
  "interview_id": "abc123",
  "speakers": [
    {
      "id": "speaker-1",
      "label": "访员",
      "color": "#1890ff",
      "chunk_id": null
    },
    {
      "id": "speaker-2",
      "label": "受访者",
      "color": "#52c41a",
      "chunk_id": null
    }
  ],
  "segments": [
    {
      "id": "segment-1",
      "speaker_id": "speaker-1",
      "speaker_label": "访员",
      "start_time": 0.0,
      "end_time": 5.5,
      "transcript": "你好，请问今天感觉怎么样？",
      "confidence": 0.95,
      "prosody": {
        "pitch_mean": 150.5,
        "pitch_std": 30.2,
        "energy_mean": 0.5,
        "speech_rate": 4.5,
        "pause_ratio": 0.2
      },
      "emotion_scores": {
        "neutral": 0.6,
        "happy": 0.2,
        "sad": 0.1,
        "angry": 0.1
      },
      "lang": "zh",
      "event": null,
      "chunk_id": null
    }
  ],
  "full_text": "你好，请问今天感觉怎么样？挺好的，谢谢关心..."
}
```

---

## 获取说话人列表

### GET /api/interviews/{interview_id}/speakers

获取访谈中的所有说话人。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/speakers
```

**成功响应** (200 OK):
```json
[
  {
    "id": "speaker-1",
    "label": "访员",
    "color": "#1890ff",
    "chunk_id": null
  },
  {
    "id": "speaker-2",
    "label": "受访者",
    "color": "#52c41a",
    "chunk_id": null
  }
]
```

---

## 获取音频片段

### GET /api/interviews/{interview_id}/segments

获取所有音频片段及其分析结果。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | int | 0 | 跳过记录数 |
| `limit` | int | 100 | 返回记录数上限 |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/segments?limit=50
```

**成功响应** (200 OK):
```json
[
  {
    "id": "segment-1",
    "speaker_id": "speaker-1",
    "speaker_label": "访员",
    "start_time": 0.0,
    "end_time": 5.5,
    "transcript": "你好，请问今天感觉怎么样？",
    "confidence": 0.95,
    "prosody": {
      "pitch_mean": 150.5,
      "pitch_std": 30.2,
      "energy_mean": 0.5,
      "speech_rate": 4.5,
      "pause_ratio": 0.2
    },
    "emotion_scores": {
      "neutral": 0.6,
      "happy": 0.2
    },
    "lang": "zh",
    "event": null,
    "chunk_id": null
  }
]
```

---

## 获取情绪分析结果

### GET /api/interviews/{interview_id}/emotion

获取情绪分析结果和汇总。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/emotion
```

**成功响应** (200 OK):
```json
{
  "interview_id": "abc123",
  "emotion_nodes": [
    {
      "id": "emotion-1",
      "timestamp": 10.5,
      "source": "audio",
      "label": "紧张",
      "intensity": 0.8,
      "confidence": 0.9
    }
  ],
  "summary": {
    "dominant_emotion": "neutral",
    "emotion_distribution": {
      "neutral": 0.5,
      "happy": 0.2,
      "sad": 0.15,
      "angry": 0.1,
      "anxious": 0.05
    },
    "stress_signals": 3,
    "avoidance_signals": 2,
    "confidence_score": 0.75
  },
  "signals": [
    {
      "timestamp": 120.5,
      "type": "stress",
      "intensity": 0.8,
      "indicator": "语速异常加快"
    }
  ]
}
```

---

## 获取时间线数据

### GET /api/interviews/{interview_id}/timeline

获取完整时间线数据，包含所有分析结果。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/timeline
```

**成功响应** (200 OK):
```json
{
  "interview_id": "abc123",
  "duration": 3600.5,
  "speakers": [...],
  "segments": [...],
  "keyframes": [...],
  "face_frames": [...],
  "emotion_nodes": [...]
}
```

---

## 获取关键帧

### GET /api/interviews/{interview_id}/keyframes

获取视频关键帧列表。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/keyframes
```

**成功响应** (200 OK):
```json
[
  {
    "id": "keyframe-1",
    "timestamp": 0.0,
    "frame_idx": 0,
    "scene_len": 150,
    "frame_path": "/data/keyframes/abc123/frame_0000.jpg"
  },
  {
    "id": "keyframe-2",
    "timestamp": 5.0,
    "frame_idx": 150,
    "scene_len": 200,
    "frame_path": "/data/keyframes/abc123/frame_0150.jpg"
  }
]
```

---

## 获取面部帧数据

### GET /api/interviews/{interview_id}/faces

获取面部帧分析数据。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | int | 0 | 跳过记录数 |
| `limit` | int | 100 | 返回记录数上限 |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/faces?limit=50
```

**成功响应** (200 OK):
```json
[
  {
    "id": "face-1",
    "timestamp": 0.5,
    "frame_path": "/data/faces/abc123/frame_0001.jpg",
    "face_bbox": [100, 100, 300, 300],
    "action_units": {
      "AU1": 0.2,
      "AU6": 0.8,
      "AU12": 0.9
    },
    "emotion_scores": {
      "happy": 0.75,
      "neutral": 0.2,
      "surprised": 0.05
    }
  }
]
```

---

## 获取分析报告

### GET /api/interviews/{interview_id}/report

获取访谈分析报告。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/abc123/report
```

**成功响应** (200 OK):
```json
{
  "interview_id": "abc123",
  "metadata": {
    "filename": "interview.mp4",
    "duration": 3600.5,
    "created_at": "2026-04-02T10:00:00Z"
  },
  "transcript": "完整转录文本...",
  "emotion_summary": {
    "dominant_emotion": "neutral",
    "stress_level": "low",
    "confidence_level": "high"
  },
  "signals": [
    {
      "timestamp": 120.5,
      "type": "stress",
      "description": "语速异常加快，可能表示紧张"
    }
  ],
  "key_moments": [
    {
      "timestamp": 300.0,
      "description": "情绪波动明显",
      "emotion_change": "neutral → anxious"
    }
  ]
}
```
