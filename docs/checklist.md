# 跨平台兼容性适配检查清单

本文档提供了完整的检查清单，用于验证跨平台兼容性适配是否完成。请在每个检查项完成后打勾。

---

## 一、依赖管理检查清单

### 1.1 依赖文件创建
- [ ] `requirements-base.txt` 已创建
- [ ] `requirements-cuda.txt` 已创建
- [ ] `requirements-mps.txt` 已创建
- [ ] `requirements-cpu.txt` 已更新
- [ ] `requirements.txt` 已更新（包含安装说明）

### 1.2 依赖文件内容验证
- [ ] `requirements-base.txt` 包含所有非 PyTorch 依赖
- [ ] `requirements-cuda.txt` 包含正确的 CUDA 12.1 索引 URL
- [ ] `requirements-cuda.txt` PyTorch 版本为 2.5.1+cu121
- [ ] `requirements-mps.txt` PyTorch 版本为 2.5.1
- [ ] `requirements-cpu.txt` PyTorch 版本为 2.5.1+cpu
- [ ] 所有依赖版本号一致

### 1.3 安装脚本验证
- [ ] `scripts/install_deps.py` 已创建
- [ ] 脚本能正确检测 macOS
- [ ] 脚本能正确检测 Linux
- [ ] 脚本能正确检测 Windows
- [ ] 脚本能正确检测 CUDA 可用性
- [ ] 脚本支持 `--platform` 参数
- [ ] 脚本支持 `--verbose` 参数
- [ ] 脚本有完善的错误处理

---

## 二、字体管理检查清单

### 2.1 字体管理模块
- [ ] `src/utils/fonts.py` 已创建
- [ ] `FontManager` 类实现完整
- [ ] 支持 macOS 字体路径
- [ ] 支持 Linux 字体路径
- [ ] 支持 Windows 字体路径
- [ ] 有 fallback 字体机制
- [ ] `get_font_path()` 方法正常工作
- [ ] `register_fonts()` 方法正常工作

### 2.2 报告生成器修改
- [ ] `src/services/report/generator.py` 已修改
- [ ] 删除了硬编码字体路径（第 18-19 行）
- [ ] 导入了 `FontManager`
- [ ] 在 `__init__()` 中调用 `FontManager.register_fonts()`
- [ ] 字体引用已更新（STHeiti -> CN）
- [ ] 有字体缺失的错误处理

### 2.3 字体安装验证
- [ ] macOS 下字体可用
- [ ] Ubuntu 下安装了 `fonts-noto-cjk` 或其他中文字体
- [ ] 字体验证命令正常工作：`fc-list :lang=zh`
- [ ] Python 字体检测正常：`FontManager.get_font_path('cn_font')`

---

## 三、系统依赖检测检查清单

### 3.1 系统检测模块
- [ ] `src/utils/system_check.py` 已创建
- [ ] `SystemChecker` 类实现完整
- [ ] `check_ffmpeg()` 方法正常工作
- [ ] `check_gpu()` 方法正常工作
- [ ] `check_fonts()` 方法正常工作
- [ ] `full_check()` 方法正常工作
- [ ] 错误信息包含安装指南

### 3.2 音频处理器修改
- [ ] `src/services/audio/processor.py` 已修改
- [ ] 添加了 ffmpeg 检测
- [ ] ffmpeg 缺失时有友好错误提示
- [ ] 不影响正常功能

### 3.3 启动检测
- [ ] `src/api/main.py` 已修改
- [ ] 启动时执行系统检测
- [ ] 检测结果记录到日志
- [ ] 缺失依赖时有警告

### 3.4 系统检测 API（可选）
- [ ] `src/api/routes/system.py` 已创建
- [ ] `/api/system/check` 端点实现
- [ ] 返回格式正确
- [ ] 已添加到 API 路由

---

## 四、设备管理检查清单

### 4.1 设备选择逻辑
- [ ] `src/core/config.py` 已更新
- [ ] `get_device()` 返回标准化设备名（cuda/mps/cpu）
- [ ] 所有推理引擎使用统一设备选择逻辑
- [ ] 设备选择有详细日志

### 4.2 GPU 内存清理
- [ ] `src/utils/gpu.py` 已创建（或已更新）
- [ ] 统一的 GPU 内存清理函数
- [ ] 支持 CUDA 内存清理
- [ ] 支持 MPS 内存清理
- [ ] 所有引擎使用统一清理函数

### 4.3 设备信息日志
- [ ] 启动时记录 GPU 信息
- [ ] 模型加载时记录设备信息
- [ ] 日志格式清晰易读

---

## 五、Docker 配置检查清单

### 5.1 GPU Dockerfile
- [ ] `docker/Dockerfile.gpu` 已更新
- [ ] PyTorch 版本为 2.5.1+cu121
- [ ] 安装了中文字体（fonts-noto-cjk）
- [ ] 基础镜像为 `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`
- [ ] 依赖安装方式正确

### 5.2 CPU Dockerfile
- [ ] `docker/Dockerfile.cpu` 已更新
- [ ] PyTorch 版本为 2.5.1+cpu
- [ ] 安装了中文字体
- [ ] 基础镜像为 `python:3.10-slim`
- [ ] 依赖安装方式正确

### 5.3 Docker Compose
- [ ] `docker/docker-compose.yml` 已检查
- [ ] GPU 服务配置正确
- [ ] CPU 服务配置正确
- [ ] 卷挂载正确
- [ ] 环境变量正确

### 5.4 Docker 构建测试
- [ ] CPU 版本 Docker 镜像构建成功
- [ ] GPU 版本 Docker 镜像构建成功
- [ ] Docker 容器启动正常
- [ ] 基本功能测试通过

---

## 六、macOS 环境测试检查清单

### 6.1 环境准备
- [ ] Python 3.9+ 已安装
- [ ] 虚拟环境已创建
- [ ] 依赖安装成功（使用 `requirements-mps.txt`）
- [ ] ffmpeg 已安装（`brew install ffmpeg`）

### 6.2 功能测试
- [ ] 单元测试全部通过：`pytest tests/`
- [ ] API 服务启动正常
- [ ] 音频提取功能正常
- [ ] 语音识别功能正常（SenseVoice）
- [ ] 说话人分离功能正常（pyannote）
- [ ] 音频分离功能正常（demucs）
- [ ] 人脸分析功能正常（MediaPipe）
- [ ] 情绪识别功能正常（transformers）
- [ ] PDF 生成功能正常

### 6.3 GPU 加速测试
- [ ] MPS 可用：`torch.backends.mps.is_available()`
- [ ] SenseVoice 使用 MPS 加速
- [ ] pyannote 使用 MPS 加速
- [ ] demucs 使用 MPS 加速
- [ ] transformers 使用 MPS 加速

### 6.4 性能测试
- [ ] 记录了各模块的处理时间
- [ ] 性能数据已保存

---

## 七、Ubuntu + RTX 4090 环境测试检查清单

### 7.1 环境准备
- [ ] Ubuntu 22.04+ 已安装
- [ ] NVIDIA 驱动已安装（CUDA 12.1+）
- [ ] Python 3.9+ 已安装
- [ ] 虚拟环境已创建
- [ ] 依赖安装成功（使用 `requirements-cuda.txt`）
- [ ] ffmpeg 已安装（`apt install ffmpeg`）
- [ ] 中文字体已安装（`apt install fonts-noto-cjk`）

### 7.2 CUDA 验证
- [ ] `nvidia-smi` 命令正常
- [ ] CUDA 版本正确：`nvcc --version`
- [ ] PyTorch CUDA 可用：`torch.cuda.is_available()`
- [ ] GPU 名称正确：`torch.cuda.get_device_name(0)`
- [ ] GPU 数量正确：`torch.cuda.device_count()`

### 7.3 功能测试
- [ ] 单元测试全部通过：`pytest tests/`
- [ ] API 服务启动正常
- [ ] 音频提取功能正常
- [ ] 语音识别功能正常（faster-whisper 或 SenseVoice）
- [ ] 说话人分离功能正常（pyannote）
- [ ] 音频分离功能正常（demucs）
- [ ] 人脸分析功能正常（MediaPipe）
- [ ] 情绪识别功能正常（transformers）
- [ ] PDF 生成功能正常

### 7.4 GPU 加速测试
- [ ] CUDA 可用：`torch.cuda.is_available()`
- [ ] faster-whisper 使用 CUDA 加速
- [ ] SenseVoice 使用 CUDA 加速
- [ ] pyannote 使用 CUDA 加速
- [ ] demucs 使用 CUDA 加速
- [ ] transformers 使用 CUDA 加速

### 7.5 性能测试
- [ ] 记录了各模块的处理时间
- [ ] 性能数据已保存
- [ ] RTX 4090 比 macOS MPS 快 3 倍以上

### 7.6 GPU 内存测试
- [ ] GPU 内存使用合理（不超过 80%）
- [ ] 模型卸载后内存释放正常
- [ ] 长时间运行无内存泄漏

---

## 八、文档检查清单

### 8.1 README 更新
- [ ] README.md 已更新
- [ ] 包含平台特定的安装指南
- [ ] 包含依赖安装说明
- [ ] 包含字体安装说明
- [ ] 包含 ffmpeg 安装说明
- [ ] 包含环境变量说明

### 8.2 跨平台文档
- [ ] `docs/CROSS_PLATFORM.md` 已更新
- [ ] 包含最新的兼容性分析
- [ ] 包含实施状态

### 8.3 API 文档
- [ ] API 文档已更新
- [ ] 包含系统检测端点文档（如有）

### 8.4 故障排除文档
- [ ] 创建了故障排除指南
- [ ] 包含常见问题及解决方案
- [ ] 包含平台特定的问题

---

## 九、代码质量检查清单

### 9.1 代码规范
- [ ] 代码符合 PEP 8 规范
- [ ] 使用了类型注解
- [ ] 有详细的文档字符串
- [ ] 无硬编码路径

### 9.2 错误处理
- [ ] 所有关键路径有错误处理
- [ ] 错误信息清晰友好
- [ ] 错误信息包含解决方案

### 9.3 日志记录
- [ ] 关键操作有日志记录
- [ ] 日志级别合理
- [ ] 日志格式统一

### 9.4 测试覆盖
- [ ] 新增模块有单元测试
- [ ] 测试覆盖率 > 80%
- [ ] 边界情况有测试

---

## 十、最终验收检查清单

### 10.1 功能验收
- [ ] macOS 环境下所有功能正常运行
- [ ] Ubuntu + RTX 4090 环境下所有功能正常运行
- [ ] PDF 生成功能在两个平台都能正常工作
- [ ] 音频处理功能在两个平台都能正常工作
- [ ] GPU 加速在两个平台都能正常使用

### 10.2 性能验收
- [ ] RTX 4090 环境下推理速度比 macOS MPS 快 3 倍以上
- [ ] GPU 内存使用合理（不超过 80%）
- [ ] CPU 环境下功能正常（作为 fallback）

### 10.3 兼容性验收
- [ ] macOS 环境不受影响
- [ ] Ubuntu 环境功能完整
- [ ] Docker 环境正常
- [ ] 无平台特定 bug

### 10.4 文档验收
- [ ] README 包含平台特定的安装指南
- [ ] 代码注释清晰说明平台差异
- [ ] 错误提示包含平台特定的解决方案

---

## 检查清单使用说明

### 使用方法
1. **逐项检查**：按照清单顺序逐项检查
2. **标记完成**：完成的项打勾 `[x]`
3. **记录问题**：未通过的项记录问题和解决方案
4. **定期回顾**：每周回顾一次进度

### 优先级说明
- **高优先级**：必须完成，影响核心功能
- **中优先级**：应该完成，影响用户体验
- **低优先级**：可选完成，优化项

### 问题记录模板

| 检查项 | 问题描述 | 解决方案 | 状态 | 负责人 |
|--------|---------|---------|------|--------|
| 示例 | Ubuntu 下字体缺失 | 安装 fonts-noto-cjk | 已解决 | 张三 |

---

## 附录：快速检查命令

### macOS 环境检查
```bash
# 检查 Python 版本
python --version

# 检查 ffmpeg
ffmpeg -version

# 检查字体
fc-list :lang=zh

# 检查 MPS
python -c "import torch; print(f'MPS available: {torch.backends.mps.is_available()}')"

# 运行测试
pytest tests/

# 启动服务
python -m uvicorn src.api.main:app --reload
```

### Ubuntu 环境检查
```bash
# 检查 Python 版本
python --version

# 检查 ffmpeg
ffmpeg -version

# 检查字体
fc-list :lang=zh

# 检查 CUDA
nvidia-smi
nvcc --version

# 检查 PyTorch CUDA
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}')"

# 运行测试
pytest tests/

# 启动服务
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### Docker 环境检查
```bash
# 构建 CPU 版本
docker-compose -f docker/docker-compose.yml build api-cpu

# 构建 GPU 版本
docker-compose -f docker/docker-compose.yml build api-gpu

# 运行 CPU 版本
docker-compose -f docker/docker-compose.yml up api-cpu

# 运行 GPU 版本
docker-compose -f docker/docker-compose.yml --profile gpu up api-gpu

# 检查容器日志
docker logs interview-ai-cpu
docker logs interview-ai-gpu
```

---

## 检查清单统计

| 类别 | 检查项数量 | 已完成 | 完成率 |
|------|-----------|--------|--------|
| 一、依赖管理 | 14 | 0 | 0% |
| 二、字体管理 | 11 | 0 | 0% |
| 三、系统依赖检测 | 11 | 0 | 0% |
| 四、设备管理 | 9 | 0 | 0% |
| 五、Docker 配置 | 11 | 0 | 0% |
| 六、macOS 环境测试 | 16 | 0 | 0% |
| 七、Ubuntu 环境测试 | 24 | 0 | 0% |
| 八、文档 | 9 | 0 | 0% |
| 九、代码质量 | 11 | 0 | 0% |
| 十、最终验收 | 11 | 0 | 0% |
| **总计** | **127** | **0** | **0%** |

---

**最后更新时间**: 2026-04-01  
**负责人**: 待分配  
**预计完成时间**: 待定
