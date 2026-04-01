# 跨平台兼容性适配规格文档

## 项目概述

### 目标
将基于 macOS 开发的 Interview AI 项目适配到 Ubuntu + NVIDIA GPU (RTX 4090) 环境，同时确保在 macOS 环境下仍能正常运行。

### 背景
当前项目在 macOS 环境下开发，使用了以下平台特定功能：
- Apple MPS (Metal Performance Shaders) GPU 加速
- macOS 系统字体路径
- macOS 特定的依赖版本

需要适配到 Ubuntu + NVIDIA RTX 4090 环境，使用 CUDA 加速。

### 约束条件
1. **不影响 macOS 环境**：所有修改必须保证在 macOS 下仍能正常运行
2. **最小化修改**：优先使用平台检测和 fallback 机制，而非创建分支代码
3. **向后兼容**：保持现有 API 接口不变
4. **性能优化**：充分利用 RTX 4090 的性能优势

---

## 兼容性问题分析

### 1. 依赖管理问题（高优先级）

#### 问题描述
`requirements.txt` 中硬编码了 CUDA 版本的 PyTorch：
```
torch==2.5.1+cu121
torchaudio==2.5.1+cu121
```

这会导致：
- **macOS 无法安装**：cu121 版本仅支持 Linux/Windows
- **Ubuntu CPU 环境无法安装**：需要 CPU 版本
- **版本冲突**：不同环境需要不同版本

#### 影响范围
- 所有依赖 PyTorch 的模块
- Docker 构建流程
- 本地开发环境

#### 解决方案
创建平台特定的依赖文件：
```
requirements.txt              # 通用依赖（不含 PyTorch）
requirements-cuda.txt         # CUDA 版本（Ubuntu + NVIDIA GPU）
requirements-mps.txt          # MPS 版本（macOS Apple Silicon）
requirements-cpu.txt          # CPU 版本（已存在，需更新）
```

---

### 2. PDF 字体路径硬编码（高优先级）

#### 问题描述
`src/services/report/generator.py` 第 18-19 行：
```python
pdfmetrics.registerFont(TTFont("STHeiti", "/System/Library/Fonts/STHeiti Light.ttc"))
pdfmetrics.registerFont(TTFont("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf"))
```

这会导致：
- **Ubuntu 下找不到字体**：路径不存在
- **PDF 生成失败**：无法渲染中文

#### 影响范围
- 报告生成功能
- PDF 导出功能

#### 解决方案
实现平台检测和字体 fallback 机制：
1. 检测操作系统类型
2. 根据系统选择合适的字体路径
3. 如果字体不存在，使用备用字体或提示安装

---

### 3. ffmpeg 系统依赖检测（中优先级）

#### 问题描述
`src/services/audio/processor.py` 第 35-46 行直接调用 `ffmpeg`：
```python
subprocess.run(cmd, check=True, capture_output=True)
```

这会导致：
- **ffmpeg 未安装时报错不明确**
- **用户不知道如何安装**

#### 影响范围
- 音频提取功能
- 视频处理功能

#### 解决方案
添加 ffmpeg 检测和友好的错误提示：
1. 在调用前检测 ffmpeg 是否安装
2. 未安装时提供平台特定的安装指南
3. 记录详细的错误日志

---

### 4. GPU 设备选择逻辑（低优先级）

#### 问题描述
当前代码已有设备选择逻辑，但存在以下问题：
1. `src/core/config.py` 的 `get_device()` 返回 `"cuda:0"` 而非 `"cuda"`
2. 部分引擎的设备清理逻辑不统一

#### 影响范围
- 所有推理引擎
- GPU 内存管理

#### 解决方案
统一设备选择和清理逻辑：
1. 标准化设备返回值（cuda/mps/cpu）
2. 统一 GPU 内存清理方法
3. 添加设备信息日志

---

### 5. Docker 配置优化（中优先级）

#### 问题描述
当前 Docker 配置存在以下问题：
1. `Dockerfile.gpu` 使用 PyTorch 2.1.0，但 requirements.txt 要求 2.5.1
2. 缺少中文字体安装
3. 缺少 ffmpeg 检测

#### 影响范围
- Docker 部署
- 生产环境

#### 解决方案
更新 Docker 配置：
1. 统一 PyTorch 版本
2. 安装中文字体
3. 添加依赖检测

---

## 技术方案设计

### 方案 1：依赖管理重构

#### 文件结构
```
requirements-base.txt         # 基础依赖（不含 PyTorch）
requirements-cuda.txt         # CUDA 版本
requirements-mps.txt          # MPS 版本（macOS）
requirements-cpu.txt          # CPU 版本
requirements.txt              # 主文件（根据平台自动选择）
```

#### 安装脚本
创建 `scripts/install_deps.py`：
```python
import platform
import subprocess
import sys

def install_dependencies():
    system = platform.system()
    
    # 安装基础依赖
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-base.txt"])
    
    # 根据平台安装 PyTorch
    if system == "Darwin":  # macOS
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-mps.txt"])
    elif system == "Linux":
        # 检测是否有 NVIDIA GPU
        try:
            import torch
            if torch.cuda.is_available():
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-cuda.txt"])
            else:
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-cpu.txt"])
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-cpu.txt"])
    else:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-cpu.txt"])
```

---

### 方案 2：字体管理模块

#### 新建模块
创建 `src/utils/fonts.py`：

```python
import platform
import os
from pathlib import Path
from typing import Optional, Dict

class FontManager:
    FONT_REGISTRY = {
        "Darwin": {
            "cn_font": "/System/Library/Fonts/STHeiti Light.ttc",
            "unicode_font": "/Library/Fonts/Arial Unicode.ttf",
        },
        "Linux": {
            "cn_font": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "unicode_font": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        },
        "Windows": {
            "cn_font": "C:/Windows/Fonts/msyh.ttc",
            "unicode_font": "C:/Windows/Fonts/arial.ttf",
        },
    }
    
    FALLBACK_FONTS = {
        "cn_font": [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
        ],
        "unicode_font": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ],
    }
    
    @classmethod
    def get_font_path(cls, font_type: str) -> Optional[str]:
        system = platform.system()
        registry = cls.FONT_REGISTRY.get(system, cls.FONT_REGISTRY["Linux"])
        
        primary_path = registry.get(font_type)
        if primary_path and os.path.exists(primary_path):
            return primary_path
        
        for fallback in cls.FALLBACK_FONTS.get(font_type, []):
            if os.path.exists(fallback):
                return fallback
        
        return None
    
    @classmethod
    def register_fonts(cls) -> Dict[str, bool]:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        results = {}
        
        cn_path = cls.get_font_path("cn_font")
        if cn_path:
            try:
                pdfmetrics.registerFont(TTFont("CN", cn_path))
                results["cn_font"] = True
            except Exception:
                results["cn_font"] = False
        else:
            results["cn_font"] = False
        
        unicode_path = cls.get_font_path("unicode_font")
        if unicode_path:
            try:
                pdfmetrics.registerFont(TTFont("ArialUnicode", unicode_path))
                results["unicode_font"] = True
            except Exception:
                results["unicode_font"] = False
        
        return results
```

---

### 方案 3：系统依赖检测

#### 新建模块
创建 `src/utils/system_check.py`：

```python
import shutil
import platform
from typing import Dict, List, Tuple

class SystemChecker:
    @staticmethod
    def check_ffmpeg() -> Tuple[bool, str]:
        if shutil.which("ffmpeg"):
            return True, "ffmpeg is installed"
        
        system = platform.system()
        install_guide = {
            "Darwin": "brew install ffmpeg",
            "Linux": "apt install ffmpeg  # Debian/Ubuntu\nyum install ffmpeg  # CentOS/RHEL",
            "Windows": "choco install ffmpeg  # or download from https://ffmpeg.org/download.html",
        }
        
        return False, f"ffmpeg not found. Install with:\n{install_guide.get(system, 'Visit https://ffmpeg.org')}"
    
    @staticmethod
    def check_gpu() -> Dict[str, any]:
        result = {
            "cuda_available": False,
            "cuda_version": None,
            "gpu_name": None,
            "mps_available": False,
        }
        
        try:
            import torch
            result["cuda_available"] = torch.cuda.is_available()
            if result["cuda_available"]:
                result["cuda_version"] = torch.version.cuda
                result["gpu_name"] = torch.cuda.get_device_name(0)
            result["mps_available"] = torch.backends.mps.is_available()
        except ImportError:
            pass
        
        return result
    
    @staticmethod
    def check_fonts() -> Dict[str, bool]:
        from src.utils.fonts import FontManager
        
        results = {}
        for font_type in ["cn_font", "unicode_font"]:
            path = FontManager.get_font_path(font_type)
            results[font_type] = path is not None
        
        return results
    
    @classmethod
    def full_check(cls) -> Dict[str, any]:
        ffmpeg_ok, ffmpeg_msg = cls.check_ffmpeg()
        gpu_info = cls.check_gpu()
        font_info = cls.check_fonts()
        
        return {
            "platform": platform.system(),
            "ffmpeg": {
                "available": ffmpeg_ok,
                "message": ffmpeg_msg,
            },
            "gpu": gpu_info,
            "fonts": font_info,
        }
```

---

## 实施计划

### 阶段 1：依赖管理重构（预计 2 小时）
1. 创建 `requirements-base.txt`
2. 创建 `requirements-cuda.txt`
3. 创建 `requirements-mps.txt`
4. 更新 `requirements-cpu.txt`
5. 创建 `scripts/install_deps.py`
6. 更新 README 文档

### 阶段 2：字体管理模块（预计 1.5 小时）
1. 创建 `src/utils/fonts.py`
2. 修改 `src/services/report/generator.py`
3. 添加字体安装文档
4. 测试 PDF 生成

### 阶段 3：系统依赖检测（预计 1 小时）
1. 创建 `src/utils/system_check.py`
2. 修改 `src/services/audio/processor.py`
3. 添加启动时检测
4. 添加 API 端点 `/api/system/check`

### 阶段 4：设备管理优化（预计 0.5 小时）
1. 统一设备选择逻辑
2. 统一 GPU 内存清理
3. 添加设备信息日志

### 阶段 5：Docker 配置更新（预计 1 小时）
1. 更新 `Dockerfile.gpu`
2. 更新 `Dockerfile.cpu`
3. 添加字体安装
4. 测试 Docker 构建

### 阶段 6：测试和验证（预计 2 小时）
1. macOS 环境测试
2. Ubuntu + RTX 4090 环境测试
3. Docker 环境测试
4. 性能基准测试

---

## 风险评估

### 高风险项
1. **PyTorch 版本差异**：不同版本可能有 API 变化
   - 缓解措施：使用相同的大版本号（2.x）

### 中风险项
1. **字体缺失**：Ubuntu 默认可能没有中文字体
   - 缓解措施：提供多个 fallback 路径和安装指南

2. **CUDA 版本兼容性**：不同 CUDA 版本可能有差异
   - 缓解措施：明确指定 CUDA 12.1

### 低风险项
1. **ffmpeg 路径差异**：不同系统 ffmpeg 路径可能不同
   - 缓解措施：使用 `shutil.which()` 检测

---

## 验收标准

### 功能验收
- [ ] macOS 环境下所有功能正常运行
- [ ] Ubuntu + RTX 4090 环境下所有功能正常运行
- [ ] PDF 生成功能在两个平台都能正常工作
- [ ] 音频处理功能在两个平台都能正常工作
- [ ] GPU 加速在两个平台都能正常使用

### 性能验收
- [ ] RTX 4090 环境下推理速度比 macOS MPS 快 3 倍以上
- [ ] GPU 内存使用合理（不超过 80%）
- [ ] CPU 环境下功能正常（作为 fallback）

### 文档验收
- [ ] README 包含平台特定的安装指南
- [ ] 代码注释清晰说明平台差异
- [ ] 错误提示包含平台特定的解决方案

---

## 附录

### A. 平台支持矩阵

| 功能 | macOS (MPS) | Ubuntu (CUDA) | Ubuntu (CPU) |
|------|:-----------:|:-------------:|:------------:|
| 语音识别 (faster-whisper) | ⚠️ CPU fallback | ✅ GPU 加速 | ✅ |
| 语音识别 (SenseVoice) | ✅ MPS 加速 | ✅ CUDA 加速 | ✅ |
| 说话人分离 (pyannote) | ✅ MPS 加速 | ✅ CUDA 加速 | ✅ |
| 音频分离 (demucs) | ✅ MPS 加速 | ✅ CUDA 加速 | ✅ |
| 人脸分析 (MediaPipe) | ✅ | ✅ | ✅ |
| 情绪识别 (transformers) | ✅ MPS 加速 | ✅ CUDA 加速 | ✅ |
| PDF 生成 | ✅ | ✅ | ✅ |

### B. 依赖版本对照表

| 依赖 | macOS (MPS) | Ubuntu (CUDA) | Ubuntu (CPU) |
|------|------------|---------------|--------------|
| Python | 3.9+ | 3.9+ | 3.9+ |
| PyTorch | 2.5.1 | 2.5.1+cu121 | 2.5.1+cpu |
| CUDA | - | 12.1 | - |
| ffmpeg | 系统安装 | 系统安装 | 系统安装 |

### C. 字体安装指南

#### Ubuntu/Debian
```bash
# 推荐：Noto CJK（包含中日韩文字）
sudo apt install fonts-noto-cjk

# 或：文泉驿微米黑（轻量）
sudo apt install fonts-wqy-microhei

# 或：思源黑体
sudo apt install fonts-noto-cjk-extra
```

#### macOS
系统已内置中文字体，无需额外安装。

#### 验证字体安装
```bash
# 列出已安装的中文字体
fc-list :lang=zh

# 或使用 Python
python -c "from src.utils.fonts import FontManager; print(FontManager.get_font_path('cn_font'))"
```
