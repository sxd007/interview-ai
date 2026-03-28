# 可行性分析报告

> **版本**: v0.1 | **日期**: 2026-03-19 | **状态**: 待审阅

---

## 一、项目背景与目标

**项目名称**: 访谈视频智能处理系统 (Interview Intelligence System)

**核心目标**: 对访谈视频进行多维度智能分析，支持心理研究、合规调查等场景下的深度复盘与决策分析。

**目标用户**:
- 企业内部合规调查访谈记录分析
- 心理咨询与行为研究
- 面试复盘与评估

---

## 二、技术可行性评估

### 2.1 视频分析模块

| 功能 | 推荐方案 | 模型规模 | 硬件需求 | 可行性 |
|------|---------|---------|---------|--------|
| 关键帧提取 | PySceneDetect + 自定义采样 | — | CPU | ✅ 高 |
| 人物检测 | YOLOv8n-face / YOLOv8s-pose | 3-50M | GPU@4GB | ✅ 高 |
| 面部情绪识别 | MediaPipe Blendshapes + LSTM | ~500K | GPU@2GB | ✅ 高 |
| 微表情/微动作识别 | MicroEmo / LFD-TCMEN 框架 | 需微调 | GPU@6GB+ | ⚠️ 中 |
| 动作识别 | TinyLLaVA-Video / SmolVLM2 | 500M-4B | GPU@4-8GB | ✅ 中高 |
| 视频理解综合 | Qwen2.5-VL-7B / Qwen3-VL-8B | 7-8B | GPU@8-12GB | ⚠️ 中 |

### 2.2 音频分析模块

| 功能 | 推荐方案 | 模型规模 | 硬件需求 | 可行性 |
|------|---------|---------|---------|--------|
| 音频提取 | FFmpeg | — | CPU | ✅ 高 |
| 去噪增强 | Demucs (htdemucs_ft) | ~300M | GPU@4GB | ✅ 高 |
| 音频可视化 | librosa + matplotlib | — | CPU | ✅ 高 |
| 人声分离/区分 | Demucs / pyannote.audio (VAD) | ~300M | GPU@4GB | ✅ 高 |
| 语音转文字 (STT) | Whisper Large V3 Turbo / Qwen3-ASR-1.7B | 1-3B | GPU@4-8GB | ✅ 高 |
| 时间戳对齐 | WhisperX / Qwen3-ForcedAligner | — | CPU | ✅ 高 |
| 说话人分离 (Diarization) | pyannote.audio 3.1 / Diarize (Sortformer) | ~1B | GPU@4GB / CPU | ✅ 高 |
| 声音基线/韵律分析 | prosodylab-aligner + praat-parselmouth | — | CPU | ✅ 高 |
| 声音情绪识别 | emotion2vec+ (FunASR) / HuBERT SER | ~1B | GPU@4GB | ✅ 高 |

### 2.3 总体评估

项目在技术上 **可行**，核心功能(转录、说话人分离、韵律分析、面部分析)均有成熟开源方案支撑。

- **高可行性**: STT、说话人分离、降噪、面部分析 — 现有成熟方案
- **中等可行性**: 微表情 — 学术前沿，开源模型有限，需微调
- **需注意**: VLM视频理解效果良好，但长视频需分段处理

---

## 三、模型选型参考

### 3.1 模型总表

| 类别 | 推荐模型 | 规模 | 精度 | 速度 | 显存 | 许可证 |
|------|---------|------|------|------|------|--------|
| **STT** | faster-whisper large-v3-turbo | 3B | 高 | 中 | 6GB | MIT |
| **STT (轻量)** | Qwen3-ASR-1.7B | 1.7B | 中 | 快 | 4GB | Apache |
| **降噪** | Demucs htdemucs_ft | 300M | 高 | 中 | 4GB | MIT |
| **说话人分离** | pyannote/speaker-diarization-3.1 | ~1B | 高 | 中 | 4GB | MIT |
| **说话人分离 (CPU)** | Diarize (Sortformer) | ~500M | 中 | 快 | CPU | Apache |
| **声音情绪** | FunAudioLLM/emotion2vecPlus | 1B | 中 | 中 | 4GB | 需确认 |
| **面部分析** | MediaPipe Face Mesh | — | 高 | 快 | <1GB | Apache |
| **AU检测** | 自定义 + OpenFace特征 | — | 中 | 快 | 2GB | — |
| **微表情** | CNN+LSTM (自训练) | ~10M | 中低 | 中 | 2GB | — |
| **视频理解** | Qwen2.5-VL-7B / Qwen3-VL-8B | 7-8B | 高 | 慢 | 12GB | Apache |
| **视频理解 (轻量)** | SmolVLM2-2.2B | 2.2B | 中 | 中 | 4GB | SMI |

### 3.2 详细模型说明

#### 语音转文字 (STT)

**推荐: faster-whisper large-v3-turbo**
- 基于 OpenAI Whisper Large V3 Turbo，C++实现
- WER: ~10-12% (英文)，支持99+语言
- 支持时间戳精确对齐
- 推理速度比PyTorch快2-4倍

**备选: Qwen3-ASR-1.7B**
- 阿里Qwen团队，体积更小
- 中文支持良好
- 适合资源受限场景

#### 说话人分离

**推荐: pyannote.audio 3.1**
- CNRS开源，SOTA水平
- DER ~10% (VoxConverse)
- 支持重叠语音检测
- 需要 HuggingFace token (研究用免费)

**备选: Diarize (Sortformer)**
- 纯CPU运行，DER ~10.8%
- 无需申请token
- Apache 2.0许可

#### 音频降噪

**推荐: Demucs htdemucs_ft**
- Meta开源，深度学习降噪
- 保留语音质量优秀
- 支持GPU加速

#### 声音情绪识别

**推荐: emotion2vec+ (FunASR)**
- 阿里FunAudioLLM系列
- 支持7-8种情绪分类
- 细粒度情绪强度评分

#### 面部分析

**推荐: MediaPipe Face Mesh**
- Google开源，成熟稳定
- 468个3D面部关键点
- 支持实时处理
- 跨平台 (iOS/Android/Web/PC)

#### 视频理解

**推荐: Qwen3-VL-8B**
- 阿里Qwen3系列
- 支持视频输入
- 中文理解优秀
- 视觉问答、字幕生成能力强

**备选: SmolVLM2-2.2B**
- HuggingFace出品
- 极低资源占用 (<1GB GPU)

### 3.3 推理框架选择

| 框架 | 适用场景 | 优势 | 劣势 |
|------|---------|------|------|
| **Ollama** | 快速原型 / VLM | 一键运行，模型管理简单 | 定制性有限 |
| **vLLM** | 生产部署 | 高吞吐，PagedAttention | 配置复杂 |
| **llama.cpp** | CPU/低显存 | GGUF量化好，兼容广 | 不支持所有模型 |
| **faster-whisper** | STT专用 | C++极速 | 仅限Whisper系列 |

**建议**: 开发期用 Ollama，生产用 vLLM + faster-whisper

---

## 四、关键技术方案 (心理分析场景)

### 4.1 微表情 / 面部动作分析

传统微表情识别依赖专业数据集（如 CASME、SAMM），当前开源社区的成熟模型有限。更实用的方案是：

| 方法 | 工具 | 说明 |
|------|-----|------|
| **面部动作单元 (AU) 检测** | OpenFace 2.2 / MediaPipe Face Mesh | 检测 AU 强度（皱眉、嘴角上扬等），这是 FACS 标准方法 |
| **微表情区域放大** | MicroEmo 框架思路 | 对眼周、嘴角等区域做时序分析 |
| **情绪指标** | BlendFER-Lite + LSTM | MediaPipe Blendshapes → LSTM 时序分类 |

**推荐方案**: MediaPipe Face Mesh (检测468个面部关键点) + AU 强度计算 + LSTM 时序分类

### 4.2 声音心理信号检测

| 信号类型 | 检测方法 | 关键指标 |
|---------|---------|---------|
| **压力/紧张** | 语速变化 + 基频 (F0) 抖动 | 语速加快/减慢、F0 异常波动 |
| **回避/说谎倾向** | 填充词频率 + 沉默模式 | "嗯"、停顿模式异常 |
| **情绪波动** | 能量变化 + 音调范围 | 音量/音调突变 |
| **自信度** | 音量稳定性 + 语速一致性 | 方差分析 |

**工具链**: `praat-parselmouth` (基频/能量分析) + `prosodylab-aligner` (韵律标注) + 自定义规则引擎

---

## 五、风险评估与缓解

### 5.1 技术风险

| 风险 | 影响 | 概率 | 缓解策略 |
|------|------|------|---------|
| 微表情识别准确率低 | 高 | 中 | 作为P2功能，使用VLM辅助；可考虑外包人工标注 |
| 中文STT准确率不足 | 中 | 低 | 使用Whisper large-v3-turbo，中文训练数据充足 |
| 长视频内存溢出 | 中 | 中 | 分段处理 (每10分钟一段)，流式推理 |
| 模型下载慢/失败 | 低 | 中 | 配置镜像源，预下载机制 |
| 多说话人分离不准 | 中 | 中 | 结合视频人脸做辅助判断 |

### 5.2 项目风险

| 风险 | 影响 | 概率 | 缓解策略 |
|------|------|------|---------|
| 需求变更频繁 | 高 | 高 | 采用敏捷开发，每阶段有明确交付物 |
| 技术调研超时 | 中 | 中 | 限制调研时间，先用成熟方案 |
| 性能优化周期不足 | 中 | 中 | Phase 5 预留优化时间 |
| 测试数据不足 | 低 | 中 | 尽早收集真实访谈数据 |

### 5.3 运营风险

| 风险 | 影响 | 概率 | 缓解策略 |
|------|------|------|---------|
| 隐私合规 (访谈数据) | 高 | 低 | 完全本地处理，不上传云端 |
| GPU资源不足 | 中 | 中 | 设计CPU fallback方案 |
| 模型许可证问题 | 低 | 低 | 优先选择Apache/MIT许可模型 |

---

## 六、硬件配置建议

### 6.1 推荐配置

| 级别 | GPU | 内存 | 存储 | 适用场景 | 预估成本 |
|------|-----|------|------|---------|---------|
| **入门** | RTX 3060 12GB / Mac M2 Pro 24GB | 32GB | 1TB SSD | 开发测试、单视频处理 | ¥4000-8000 |
| **推荐** | RTX 4090 24GB | 64GB | 2TB SSD | 生产处理、批量任务 | ¥18000-25000 |
| **高性能** | A6000 48GB × 2 | 128GB | 4TB SSD | 大规模处理、团队协作 | ¥60000+ |

### 6.2 软件环境

```yaml
# 基础环境
OS: Ubuntu 22.04 LTS / macOS 14+
Python: 3.10 - 3.12
CUDA: 12.1+
cuDNN: 8.9+
Docker: 24.0+

# Python关键依赖
faster-whisper: 1.0+     # STT
pyannote.audio: 3.1+     # 说话人分离
demucs: 4.0+             # 降噪
MediaPipe: latest        # 面部分析
praat-parselmouth: latest # 韵律分析
transformers: 4.40+     # 通用
torch: 2.3+              # 深度学习框架
ffmpeg: latest           # 视频处理

# 推理服务
ollama: latest           # 模型管理
# 或
vllm: 0.4+              # 生产级推理
```

---

## 七、附录

### A. 相关资源

| 资源类型 | 链接 |
|---------|------|
| Whisper | https://github.com/openai/whisper |
| faster-whisper | https://github.com/SYSTRAN/faster-whisper |
| pyannote.audio | https://github.com/pyannote/pyannote-audio |
| Demucs | https://github.com/facebookresearch/demucs |
| MediaPipe | https://google.github.io/mediapipe/ |
| emotion2vec+ | https://www.funaudiollm.org/emotion2vec.html |
| Qwen3-VL | https://huggingface.co/Qwen/Qwen2.5-VL |
| SmolVLM2 | https://huggingface.co/HuggingFaceTB/SmolVLM2 |

### B. 许可证参考

| 模型/库 | 许可证 | 商用许可 |
|---------|--------|---------|
| Whisper | MIT | ✅ |
| faster-whisper | MIT | ✅ |
| pyannote.audio | MIT | ✅ (需申请token) |
| Demucs | MIT | ✅ |
| MediaPipe | Apache 2.0 | ✅ |
| Qwen系列 | Apache 2.0 | ✅ |
| SmolVLM2 | SMI | ✅ |
| emotion2vec+ | 需确认 | 需确认 |

### C. 评估指标说明

| 指标 | 全称 | 说明 | 目标值 |
|------|------|------|--------|
| WER | Word Error Rate | 词错误率，越低越好 | < 15% |
| DER | Diarization Error Rate | 说话人分离错误率，越低越好 | < 15% |
| PESQ | Perceptual Evaluation of Speech Quality | 语音质量感知评估，越高越好 | > 3.0 |
| RTF | Real-Time Factor | 实时因子，处理1秒音频所需时间 | < 1.0 |
