# Interview AI API 文档

> **版本**: v0.1.0
> **基础URL**: `http://localhost:8000/api`

---

## 目录

1. [概述](#概述)
2. [认证](#认证)
3. [错误处理](#错误处理)
4. [访谈管理 API](./interviews.md)
5. [处理任务 API](./process.md)
6. [管线控制 API](./pipeline.md)
7. [修正管理 API](./corrections.md)
8. [数据模型](./schemas.md)

---

## 概述

Interview AI API 提供访谈视频智能分析功能，包括：

- **访谈管理**: 上传、查询、删除访谈视频
- **处理任务**: 执行音频/视频分析管线
- **管线控制**: 管理处理阶段、审批结果
- **修正管理**: 用户修正说话人/片段信息

### 响应格式

所有 API 响应均为 JSON 格式。

**成功响应**:
```json
{
  "id": "abc123",
  "status": "completed",
  ...
}
```

**错误响应**:
```json
{
  "error_code": "VIDEO_NOT_FOUND",
  "message": "Video file not found for interview: abc123",
  "detail": {
    "interview_id": "abc123"
  },
  "timestamp": "2026-04-02T10:00:00Z"
}
```

---

## 认证

当前版本无需认证（开发环境）。

生产环境需配置 API Key：
```
Authorization: Bearer <api_key>
```

---

## 错误处理

### 错误码

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| `INTERVIEW_NOT_FOUND` | 404 | 访谈不存在 |
| `VIDEO_NOT_FOUND` | 404 | 视频文件不存在 |
| `FILE_NOT_FOUND` | 404 | 文件不存在 |
| `VALIDATION_ERROR` | 400 | 请求参数验证失败 |
| `FILE_SIZE_ERROR` | 413 | 文件大小超限 |
| `FILE_TYPE_ERROR` | 400 | 文件类型不支持 |
| `MODEL_LOAD_ERROR` | 503 | 模型加载失败 |
| `GPU_ERROR` | 503 | GPU错误 |
| `GPU_OUT_OF_MEMORY` | 503 | GPU内存不足 |
| `VIDEO_PROCESSING_ERROR` | 500 | 视频处理错误 |
| `AUDIO_PROCESSING_ERROR` | 500 | 音频处理错误 |
| `STT_PROCESSING_ERROR` | 500 | 语音转文字错误 |
| `DIARIZATION_ERROR` | 500 | 说话人分离错误 |
| `EMOTION_ANALYSIS_ERROR` | 500 | 情绪分析错误 |
| `FACE_ANALYSIS_ERROR` | 500 | 面部分析错误 |
| `PIPELINE_ERROR` | 500 | 管线处理错误 |
| `INTERNAL_ERROR` | 500 | 内部错误 |

### 错误响应示例

**验证错误 (422)**:
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "detail": {
    "errors": [
      {
        "field": "filename",
        "message": "field required",
        "type": "value_error.missing"
      }
    ]
  }
}
```

---

## 通用参数

### 分页参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | int | 0 | 跳过记录数 |
| `limit` | int | 20 | 返回记录数上限 |

### 时间格式

所有时间字段使用 ISO 8601 格式：
```
2026-04-02T10:00:00Z
```

---

## 健康检查

### GET /api/interviews/health

检查服务健康状态。

**响应**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development"
}
```
