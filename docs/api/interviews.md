# 访谈管理 API

> **基础路径**: `/api/interviews`

---

## 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/` | 创建访谈（上传视频） |
| GET | `/` | 列出访谈列表 |
| GET | `/{interview_id}` | 获取访谈详情 |
| DELETE | `/{interview_id}` | 删除访谈 |
| POST | `/{interview_id}/status` | 获取处理状态 |

---

## 健康检查

### GET /api/interviews/health

检查服务健康状态。

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/health
```

**响应**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development"
}
```

**响应字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态：`healthy` 或 `unhealthy` |
| `version` | string | API 版本号 |
| `environment` | string | 运行环境 |

---

## 创建访谈

### POST /api/interviews

上传视频文件创建新访谈。

**请求**:

- **Content-Type**: `multipart/form-data`
- **Body**: 
  - `file`: 视频文件（必需）

**请求示例**:
```bash
curl -X POST http://localhost:8000/api/interviews \
  -F "file=@interview.mp4"
```

**成功响应** (201 Created):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "interview.mp4",
  "duration": 3600.5,
  "fps": 30.0,
  "resolution": "1920x1080",
  "status": "pending",
  "error_message": null,
  "created_at": "2026-04-02T10:00:00Z",
  "chunk_duration": null,
  "chunk_count": null,
  "is_chunked": false,
  "updated_at": "2026-04-02T10:00:00Z",
  "video_url": "/data/uploads/a1b2c3d4-e5f6-7890-abcd-ef1234567890.mp4"
}
```

**响应字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 访谈唯一标识符 |
| `filename` | string | 原始文件名 |
| `duration` | float | 视频时长（秒） |
| `fps` | float | 帧率 |
| `resolution` | string | 分辨率 |
| `status` | string | 处理状态 |
| `error_message` | string | 错误信息（如有） |
| `created_at` | datetime | 创建时间 |
| `chunk_duration` | float | 分块时长 |
| `chunk_count` | int | 分块数量 |
| `is_chunked` | bool | 是否已分块 |
| `updated_at` | datetime | 更新时间 |
| `video_url` | string | 视频访问URL |

**错误响应**:

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 413 | `FILE_SIZE_ERROR` | 文件大小超过限制（默认 2GB） |
| 400 | `FILE_TYPE_ERROR` | 文件类型不支持 |
| 500 | `INTERNAL_ERROR` | 文件保存失败 |

---

## 列出访谈

### GET /api/interviews

获取访谈列表，支持分页。

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | int | 0 | 跳过记录数 |
| `limit` | int | 20 | 返回记录数上限 |

**请求示例**:
```bash
curl "http://localhost:8000/api/interviews?skip=0&limit=10"
```

**成功响应** (200 OK):
```json
{
  "total": 100,
  "interviews": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "filename": "interview1.mp4",
      "duration": 3600.5,
      "status": "completed",
      "created_at": "2026-04-02T10:00:00Z",
      ...
    },
    ...
  ]
}
```

**响应字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 总记录数 |
| `interviews` | array | 访谈列表 |

---

## 获取访谈详情

### GET /api/interviews/{interview_id}

获取指定访谈的详细信息。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl http://localhost:8000/api/interviews/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**成功响应** (200 OK):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "interview.mp4",
  "duration": 3600.5,
  "fps": 30.0,
  "resolution": "1920x1080",
  "status": "completed",
  "error_message": null,
  "created_at": "2026-04-02T10:00:00Z",
  "chunk_duration": null,
  "chunk_count": null,
  "is_chunked": false,
  "updated_at": "2026-04-02T10:30:00Z",
  "video_url": "/data/uploads/a1b2c3d4-e5f6-7890-abcd-ef1234567890.mp4"
}
```

**错误响应**:

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 404 | `INTERVIEW_NOT_FOUND` | 访谈不存在 |

---

## 删除访谈

### DELETE /api/interviews/{interview_id}

删除指定访谈及其关联数据。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl -X DELETE http://localhost:8000/api/interviews/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**成功响应** (204 No Content):
无响应体

**错误响应**:

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 404 | `INTERVIEW_NOT_FOUND` | 访谈不存在 |

---

## 获取处理状态

### POST /api/interviews/{interview_id}/status

获取访谈的处理状态。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `interview_id` | string | 访谈ID |

**请求示例**:
```bash
curl -X POST http://localhost:8000/api/interviews/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status
```

**成功响应** (200 OK):
```json
{
  "status": "processing",
  "message": "Interview status: processing"
}
```

**响应字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 当前状态 |
| `message` | string | 状态说明 |

**状态值**:

| 状态 | 说明 |
|------|------|
| `pending` | 等待处理 |
| `queued` | 已加入队列 |
| `processing` | 处理中 |
| `completed` | 已完成 |
| `failed` | 处理失败 |

**错误响应**:

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 404 | `INTERVIEW_NOT_FOUND` | 访谈不存在 |

---

## 处理状态流转

```
pending → queued → processing → completed
                    ↓
                  failed
```

| 状态 | 可转换到 |
|------|---------|
| `pending` | `queued`, `processing` |
| `queued` | `processing` |
| `processing` | `completed`, `failed` |
| `completed` | - (终态) |
| `failed` | `pending` (可重试) |
