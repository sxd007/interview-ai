# 跨平台开发分析

> **更新时间**: 2026-03-21
> **分析目的**: 评估当前项目从 macOS 迁移到 Linux + NVIDIA GPU 的兼容性

---

## 一、平台差异点汇总

### 1. PDF 字体（高优先级）

| 文件 | 行号 | 问题 |
|------|------|------|
| `src/services/report/generator.py` | 18-19 | 硬编码 macOS 字体路径 |

```python
# 当前代码（仅 macOS 可用）
pdfmetrics.registerFont(TTFont("STHeiti", "/System/Library/Fonts/STHeiti Light.ttc"))
pdfmetrics.registerFont(TTFont("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf"))
```

**修复方案**: 平台检测 + 字体 fallback

```python
import platform
import os

FONT_REGISTRY = {
    "Darwin": {
        "CN": "/System/Library/Fonts/STHeiti Light.ttc",
        "Arial": "/Library/Fonts/Arial Unicode.ttf",
    },
    "Linux": {
        "CN": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # 需安装
        "Arial": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    },
    "Windows": {
        "CN": "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
        "Arial": "C:/Windows/Fonts/arial.ttf",
    },
}

def register_fonts():
    sys = platform.system()
    fonts = FONT_REGISTRY.get(sys, FONT_REGISTRY["Linux"])
    if os.path.exists(fonts["CN"]):
        pdfmetrics.registerFont(TTFont("CN", fonts["CN"]))
    if os.path.exists(fonts["Arial"]):
        pdfmetrics.registerFont(TTFont("ArialUnicode", fonts["Arial"]))
```

**Linux 中文字体安装**:
```bash
apt install fonts-noto-cjk  # 推荐：Noto CJK 包含中日韩文字
# 或
apt install fonts-wqy-microhei  # 文泉驿微米黑（轻量）
```

---

### 2. ffmpeg 系统依赖（中优先级）

| 文件 | 行号 | 问题 |
|------|------|------|
| `src/services/audio/processor.py` | 35-46 | 直接调用 `ffmpeg`，未检测存在性 |

```python
# 当前代码（无检测）
subprocess.run(cmd, check=True, ...)
```

**修复方案**:

```python
import shutil

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found. Install:\n"
            "  macOS:  brew install ffmpeg\n"
            "  Linux:  apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )

def extract_audio(self, video_path: str) -> tuple:
    check_ffmpeg()  # 在提取前调用
    ...
```

**各平台安装方式**:

| 平台 | 命令 |
|------|------|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `apt install ffmpeg` |
| CentOS/RHEL | `yum install ffmpeg` |
| Windows | https://ffmpeg.org/download.html 或 `choco install ffmpeg` |

---

### 3. GPU 加速器选择（低优先级）

所有推理引擎使用相同的设备选择逻辑：

```python
def _get_device(self, device: Optional[str]) -> str:
    if device == "auto":
        if torch.cuda.is_available():
            return "cuda"       # NVIDIA GPU (Linux/Windows)
        elif torch.backends.mps.is_available():
            return "mps"        # Apple Silicon (macOS)
        return "cpu"
    return device
```

**各平台后端支持矩阵**:

| 模块 | CUDA (NVIDIA) | MPS (Apple) | CPU |
|------|:---:|:---:|:---:|
| faster-whisper | ✅ float16 | ❌ (fallback to CPU+int8) | ✅ int8 |
| SenseVoice (funasr) | ✅ | ✅ | ✅ |
| pyannote.audio | ✅ | ✅ | ✅ |
| demucs | ✅ | ✅ | ✅ |
| transformers (emotion) | ✅ | ✅ | ✅ |
| MediaPipe | ✅ | ✅ | ✅ |

**已知限制**: faster-whisper 底层 ctranslate2 不支持 MPS，macOS 会自动 fallback 到 CPU+int8。若使用 SenseVoice 则可利用 MPS。

---

### 4. 模型缓存路径（低优先级）

`os.path.expanduser("~/.cache/...")` 在 Linux/macOS/Windows 均兼容，无需修改。

| 模块 | 缓存路径 | 状态 |
|------|---------|------|
| faster-whisper | `~/.cache/huggingface/hub/` | ✅ |
| SenseVoice | `~/.cache/huggingface/hub/` | ✅ |
| pyannote.audio | `~/.cache/huggingface/hub/` | ✅ |
| Demucs | `~/.cache/torch/hub/hub/` | ✅ |
| MediaPipe | `~/.cache/mediapipe/` | ✅ |

---

## 二、第三方库平台支持

| 库 | Linux | macOS | Windows | 备注 |
|----|:-----:|:-----:|:-------:|------|
| faster-whisper | ✅ | ✅ | ✅ | CUDA 仅 Linux/Windows |
| funasr (SenseVoice) | ✅ | ✅ | ✅ | |
| pyannote.audio | ✅ | ✅ | ✅ | |
| demucs | ✅ | ✅ | ✅ | |
| MediaPipe | ✅ | ✅ | ✅ | |
| transformers | ✅ | ✅ | ✅ | |
| ReportLab | ✅ | ✅ | ✅ | |
| PyTorch | ✅ | ✅ | ✅ | |
| FastAPI | ✅ | ✅ | ✅ | |
| SQLAlchemy | ✅ | ✅ | ✅ | |

---

## 三、Linux + RTX 4090 适配检查清单

### 系统依赖
- [ ] NVIDIA 驱动 (CUDA 12.x)
- [ ] cuDNN (PyTorch 自动处理)
- [ ] ffmpeg (`apt install ffmpeg`)
- [ ] 中文字体 (Noto CJK 或其他)

### Python 环境
- [ ] Python 3.9+ (项目已支持)
- [ ] PyTorch with CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu121`

### 预期性能 (RTX 4090 vs M4)

| 模块 | M4 (MPS) | RTX 4090 (CUDA) |
|------|:---:|:---:|
| faster-whisper large-v3-turbo | ~1x realtime | ~5-10x realtime |
| SenseVoice | ~1x realtime | ~3-5x realtime |
| pyannote.audio | ~1x | ~3x |
| demucs | ~0.5x | ~5x |
| MediaPipe | ~0.3x | ~2x |

RTX 4090 预期比 M4 快 **3-10 倍**。

---

## 四、开发路径建议

### 推荐: 先 macOS 再适配

```
阶段 1: macOS 开发调试
    └── 快速迭代、功能验证

阶段 2: 提取平台抽象层
    ├── 字体 fallback 机制
    ├── ffmpeg 检测装饰器
    └── GPU 选择器配置化

阶段 3: Linux + CUDA 验证
    ├── 字体安装
    ├── CUDA 环境
    └── 性能基准测试

阶段 4: Docker 部署 (可选)
    ├── CPU Docker: 开发/CI
    └── GPU Docker (nvidia-docker): 生产
```

**为什么不同时多平台开发**: 平台差异点少（主要就字体和 ffmpeg），抽取抽象层后适配成本低。先 macOS 开发效率更高。

---

## 五、待修复项

| 优先级 | 文件 | 问题 | 预估工时 |
|:------:|------|------|:--------:|
| 高 | `src/services/report/generator.py` | 字体路径硬编码 | 1h |
| 中 | `src/services/audio/processor.py` | ffmpeg 无检测 | 30min |
| 低 | `src/inference/stt/engine.py` | MPS fallback 日志 | 15min |
| 低 | `scripts/download_models.py` | 字体下载 | 15min |

---

## 六、已验证的模型兼容性

所有模型均支持 CUDA，在 Linux + RTX 4090 上应能正常工作。

| 模型 | 状态 | 缓存位置 |
|------|:----:|---------|
| FunAudioLLM/SenseVoiceSmall | ✅ | `models/` |
| pyannote/segmentation-3.0 | ✅ | `models/` |
| pyannote/speaker-diarization-3.1 | ✅ | `models/` |
| mobiuslabsgmbh/faster-whisper-large-v3-turbo | ✅ | `~/.cache/huggingface/hub/` |
| demucs htdemucs_ft | ✅ | `~/.cache/torch/hub/hub/` |
| MediaPipe face_landmarker.task | ✅ | `~/.cache/mediapipe/` |
