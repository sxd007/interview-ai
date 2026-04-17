# 人脸分析模块修复报告

## 问题诊断

### 错误信息
```
ExternalFile must specify at least one of 'file_content', 'file_name', 'file_pointer_meta' or 'file_descriptor_meta'.
```

### 根本原因
**MediaPipe 模型文件缺失**

- 需要的模型文件：`face_landmarker.task`
- 默认路径：`~/.cache/mediapipe/face_landmarker.task`
- 当前状态：文件不存在（MediaPipe 缓存目录未创建）

### 问题分析

1. **错误触发机制**：
   - 在 `src/inference/face/engine.py` 中，当模型文件不存在时，`self.model_path` 被设置为 `None`
   - MediaPipe 的 `BaseOptions(model_asset_path=None)` 要求必须提供有效的文件路径
   - 因此抛出 "ExternalFile must specify..." 错误

2. **影响范围**：
   - 人脸分析阶段（`face_analysis`）无法执行
   - 依赖人脸分析的情绪融合阶段（`fusion`）也会受影响

## 解决方案

### 1. 立即修复：下载缺失的模型文件

**已执行**：成功下载 MediaPipe face_landmarker.task 模型文件
- 文件大小：3.58 MB
- 保存位置：`~/.cache/mediapipe/face_landmarker.task`

### 2. 代码改进：增强错误处理和自动下载

**改进内容**：

#### a) 添加自动下载功能
```python
class FaceAnalysisEngine:
    DEFAULT_MODEL_PATH = os.path.expanduser("~/.cache/mediapipe/face_landmarker.task")
    MODEL_DOWNLOAD_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    
    def __init__(self, ..., auto_download: bool = True):
        # 如果模型不存在且 auto_download=True，自动下载
        if self.model_path and not os.path.exists(self.model_path):
            if self.auto_download:
                self._download_model()
            else:
                self.model_path = None
```

#### b) 添加友好的错误提示
```python
def _ensure_model(self):
    if self.model is None:
        if not self.model_path:
            raise RuntimeError(
                "MediaPipe face_landmarker.task model not found!\n"
                "The model file is required for face analysis.\n\n"
                "To fix this issue:\n"
                "1. Run: python scripts/download_models.py\n"
                "2. Or download manually from:\n"
                f"   {self.MODEL_DOWNLOAD_URL}\n"
                f"   And save to: {self.DEFAULT_MODEL_PATH}\n"
                "3. Or set auto_download=True when creating FaceAnalysisEngine"
            )
```

### 3. 测试验证

**测试结果**：
- ✅ 正常初始化（模型存在）：成功
- ✅ 自动下载禁用（模型不存在）：正确处理
- ✅ 友好错误消息：包含解决方案步骤

## 使用建议

### 方式 1：自动下载（推荐）
```python
from src.inference.face.engine import get_face_engine

# 默认启用自动下载
engine = get_face_engine()
```

### 方式 2：手动下载
```bash
# 运行模型下载脚本
python scripts/download_models.py

# 或手动下载
wget https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task \
  -O ~/.cache/mediapipe/face_landmarker.task
```

### 方式 3：禁用自动下载
```python
# 如果需要控制下载时机
engine = get_face_engine(auto_download=False)
```

## 改进效果

### Before（修复前）
```
错误：ExternalFile must specify at least one of 'file_content', 'file_name', 'file_pointer_meta' or 'file_descriptor_meta'.
用户困惑：不知道如何解决
```

### After（修复后）
```
情况 1：模型不存在且 auto_download=True
→ 自动下载模型，无需用户干预

情况 2：模型不存在且 auto_download=False
→ 抛出友好错误消息：
   "MediaPipe face_landmarker.task model not found!
    The model file is required for face analysis.
    
    To fix this issue:
    1. Run: python scripts/download_models.py
    2. Or download manually from:
       https://storage.googleapis.com/mediapipe-models/...
    3. Or set auto_download=True when creating FaceAnalysisEngine"
```

## 相关文件

- [src/inference/face/engine.py](file:///workdir/python_projects/interview-ai/src/inference/face/engine.py) - 人脸分析引擎（已改进）
- [scripts/download_models.py](file:///workdir/python_projects/interview-ai/scripts/download_models.py) - 模型下载脚本
- [docs/CROSS_PLATFORM.md](file:///workdir/python_projects/interview-ai/docs/CROSS_PLATFORM.md) - 跨平台文档

## 总结

✅ **问题已解决**：MediaPipe 模型文件已下载，人脸分析模块可正常工作
✅ **代码已改进**：添加了自动下载和友好的错误提示
✅ **用户体验提升**：未来遇到类似问题会自动处理或提供清晰的解决方案

---

**修复日期**：2026-04-15
**修复人员**：TRAE CN 工程化系统
