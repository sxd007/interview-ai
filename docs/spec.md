# Interview AI 项目状态审查报告

> **审查日期**: 2026-04-02
> **项目版本**: v0.1.0
> **审查范围**: 项目结构、关键算法、开发阶段、下一步规划

***

## 一、项目概述

### 1.1 项目定位

Interview AI 是一个**多模态访谈视频智能分析系统**，面向企业合规调查访谈和心理研究场景，提供：

- 音频处理：STT转录、说话人分离、降噪、韵律分析
- 视频分析：面部分析、动作单元(AU)计算、情绪识别
- 心理分析：压力信号、回避检测、情绪融合
- 可视化：时间线播放、情绪曲线、报告生成

### 1.2 技术栈

| 层次        | 技术选型                          | 版本                |
| --------- | ----------------------------- | ----------------- |
| **后端框架**  | FastAPI                       | 0.109.0           |
| **数据库**   | SQLite (开发) / PostgreSQL (生产) | SQLAlchemy 2.0.25 |
| **ML框架**  | PyTorch                       | 2.1.0             |
| **STT引擎** | faster-whisper / SenseVoice   | 1.0.0 / 1.3.0     |
| **说话人分离** | pyannote.audio                | 3.1.0             |
| **降噪**    | Demucs                        | 4.0.0             |
| **面部分析**  | MediaPipe                     | -                 |
| **声音情绪**  | Wav2Vec2 (emotion2vec+)       | -                 |
| **前端框架**  | React + TypeScript            | 18.3.1            |
| **UI组件**  | Ant Design                    | 5.22.5            |
| **可视化**   | Recharts                      | 2.15.0            |

***

## 二、项目结构分析

### 2.1 目录结构

```
interview-ai/
├── src/                          # 后端源码
│   ├── api/                      # FastAPI 路由层
│   │   ├── main.py              # 应用入口
│   │   ├── routes/              # API路由
│   │   │   ├── interviews.py    # 访谈管理
│   │   │   ├── process.py       # 处理任务
│   │   │   ├── pipeline.py      # 管线控制
│   │   │   └── corrections.py   # 修正管理
│   │   ├── schemas/             # Pydantic模型
│   │   └── deps.py              # 依赖注入
│   │
│   ├── core/                    # 核心配置
│   │   ├── config.py            # 配置管理
│   │   └── exceptions.py        # 异常定义
│   │
│   ├── models/                  # 数据模型
│   │   └── database.py          # SQLAlchemy模型
│   │
│   ├── services/                # 业务逻辑层
│   │   ├── audio/               # 音频处理
│   │   │   ├── processor.py     # 音频提取、降噪
│   │   │   └── prosody.py       # 韵律分析
│   │   ├── video/               # 视频分析
│   │   │   └── keyframe.py      # 关键帧提取
│   │   ├── emotion/             # 情绪分析
│   │   ├── pipeline/            # 处理管线
│   │   │   ├── cascade_engine.py    # 级联重处理
│   │   │   └── stage_executor.py    # 阶段执行器
│   │   ├── voice_print/         # 声纹识别
│   │   ├── interview.py         # 访谈管理
│   │   └── report/              # 报告生成
│   │
│   ├── inference/               # 模型推理层
│   │   ├── stt/                 # 语音转文字
│   │   │   ├── engine.py        # Whisper引擎
│   │   │   └── sensevoice.py    # SenseVoice引擎
│   │   ├── diarization/         # 说话人分离
│   │   ├── emotion/             # 声音情绪
│   │   ├── face/                # 面部分析
│   │   └── vad/                 # 语音活动检测
│   │
│   └── utils/                   # 工具函数
│       ├── logging.py           # 日志
│       ├── gpu.py               # GPU管理
│       ├── fonts.py             # 字体处理
│       └── system_check.py      # 系统检查
│
├── frontend/                    # React前端
│   └── src/
│       ├── components/          # UI组件
│       ├── pages/               # 页面
│       └── services/            # API调用
│
├── tests/                       # 测试
│   ├── unit/                    # 单元测试
│   └── integration/             # 集成测试
│
├── scripts/                     # 脚本
│   ├── download_models.py       # 模型下载
│   ├── install_deps.py          # 依赖安装
│   ├── test_pipeline.py         # 管线测试
│   └── split_video.py           # 视频分割
│
├── docker/                      # Docker配置
│   ├── docker-compose.yml       # 开发环境
│   └── docker-compose.prod.yml  # 生产环境
│
└── docs/                        # 文档
    ├── technical-design.md      # 技术设计
    ├── requirements-spec.md     # 需求规格
    └── DEVELOPMENT_STATUS.md    # 开发状态
```

### 2.2 数据模型架构

```
Interview (访谈)
├── VideoChunk (视频分块) - 支持长视频分段处理
│   ├── Speaker (说话人)
│   ├── AudioSegment (音频片段)
│   ├── FaceFrame (面部帧)
│   ├── Keyframe (关键帧)
│   └── EmotionNode (情绪节点)
├── PipelineStage (管线阶段) - 追踪处理进度
├── PendingChange (待处理变更) - 用户修正队列
├── AnnotationLog (标注日志) - 审计追踪
└── VoicePrintProfile (声纹档案) - 声纹识别
    ├── VoicePrintSample (声纹样本)
    └── VoicePrintMatch (声纹匹配)
```

***

## 三、关键算法分析

### 3.1 声音情绪分析 (VoiceEmotionEngine)

**位置**: `src/inference/emotion/engine.py`

**算法流程**:

```
音频输入 → Wav2Vec2特征提取 → 分类器 → 8维情绪向量
                                    ↓
                            压力/自信评分计算
```

**情绪类别**:

- neutral, happy, sad, angry, fearful, disgust, surprised, anxious

**关键指标**:

- `stress_score`: anxious + fearful + angry + sad
- `confidence_score`: neutral \* 0.5 + happy \* 0.5

**降级策略**:

- 模型加载失败时，使用基于能量和音高的简单规则分析

### 3.2 面部分析 (FaceAnalysisEngine)

**位置**: `src/inference/face/engine.py`

**算法流程**:

```
视频帧 → MediaPipe Face Mesh → 468关键点
                                    ↓
                            AU强度计算
                                    ↓
                            情绪分类
```

**动作单元 (AU) 计算**:

| AU编号 | 名称    | 计算方法        |
| ---- | ----- | ----------- |
| AU1  | 眉内角上扬 | 眉毛高度 / 眉间距离 |
| AU2  | 眉外角上扬 | 眉外角距离       |
| AU4  | 眉下垂   | 颧骨到眉毛距离     |
| AU6  | 脸颊上扬  | 眼睛开合度       |
| AU9  | 鼻子上皱  | 鼻尖上抬        |
| AU12 | 嘴角上扬  | 嘴角位置 / 嘴宽   |
| AU15 | 嘴角下压  | 嘴角下压程度      |
| AU17 | 下巴上扬  | 下巴抬升        |

**情绪映射**:

- happy = AU6 \* 3 + AU12 \* 2
- sad = AU4 \* 2 + AU15 \* 3 + AU17 \* 2
- angry = AU4 \* 2 + AU9 \* 3 + AU17 \* 2
- fearful = AU1 \* 2 + AU2 \* 2 + AU5 \* 2

### 3.3 韵律分析 (ProsodyAnalyzer)

**位置**: `src/services/audio/prosody.py`

**提取特征**:

| 特征            | 计算方法              | 用途   |
| ------------- | ----------------- | ---- |
| pitch\_mean   | librosa.pyin 基频均值 | 语调基准 |
| pitch\_std    | 基频标准差             | 语调波动 |
| energy\_mean  | RMS能量均值           | 音量基准 |
| speech\_rate  | 峰值检测 / 时长         | 语速   |
| pause\_ratio  | 1 - (语音时长/总时长)    | 停顿比例 |
| filler\_count | 短音节检测             | 填充词  |

**心理信号检测**:

- 压力信号: speech\_rate > 250字/分钟, pitch\_std > 50Hz
- 回避信号: filler\_count > 3, pause\_ratio > 0.3
- 情绪波动: energy\_std > 0.5

### 3.4 级联重处理引擎 (CascadeEngine)

**位置**: `src/services/pipeline/cascade_engine.py`

**核心功能**:

1. **变更管理**: 用户修正说话人/片段后，自动标记下游阶段需要重处理
2. **阶段失效**: 根据变更类型，自动失效相关阶段
3. **跨块合并**: 支持跨视频分块的说话人合并

**管线阶段顺序**:

```
audio_extract → denoise → diarization → stt → 
face_analysis → keyframes → prosody → emotion → fusion
```

**变更类型与失效映射**:

| 变更类型              | 失效阶段                     |
| ----------------- | ------------------------ |
| SPEAKER\_MERGE    | prosody, emotion, fusion |
| SPEAKER\_SPLIT    | prosody, emotion, fusion |
| SPEAKER\_REASSIGN | prosody, emotion, fusion |
| SEGMENT\_EDIT     | prosody, emotion, fusion |

### 3.5 多模态情绪融合

**融合策略**:

```python
fused_emotion = {
    "audio": 0.4,    # 声音情绪权重
    "video": 0.4,    # 面部情绪权重
    "prosody": 0.2   # 韵律特征权重
}
```

***

## 四、开发阶段评估

### 4.1 已完成阶段 (Phase 0-8)

| 阶段               | 完成日期       | 核心成果                      | 状态 |
| ---------------- | ---------- | ------------------------- | -- |
| Phase 0: 项目骨架    | 2026-03-19 | FastAPI框架、数据库模型、目录结构      | ✅  |
| Phase 1: 核心音频处理  | 2026-03-21 | STT、说话人分离、降噪              | ✅  |
| Phase 2: 前端界面    | 2026-03-21 | React + Ant Design        | ✅  |
| Phase 3: 面部分析    | 2026-03-21 | MediaPipe Face Mesh, AU计算 | ✅  |
| Phase 4: 情绪与韵律   | 2026-03-21 | emotion2vec+, 韵律分析        | ✅  |
| Phase 5: 可视化与融合  | 2026-03-21 | Recharts图表、情绪融合           | ✅  |
| Phase 6: 关键帧提取   | 2026-03-21 | PySceneDetect场景检测         | ✅  |
| Phase 7: PDF报告   | 2026-03-21 | ReportLab中文报告             | ✅  |
| Phase 8: STT引擎切换 | 2026-03-21 | Faster-Whisper/SenseVoice | ✅  |

### 4.2 待开发阶段 (Phase 9)

| 阶段             | 优先级 | 核心功能         | 预估工作量 |
| -------------- | --- | ------------ | ----- |
| Phase 9: 微表情检测 | P1  | CNN/LSTM时序分析 | 中     |

### 4.3 功能完成度评估

#### 核心功能完成度

| 功能模块  | 完成度  | 说明                          |
| ----- | ---- | --------------------------- |
| 视频上传  | 100% | 支持拖拽、批量上传                   |
| 视频解码  | 100% | FFmpeg集成                    |
| 音频提取  | 100% | FFmpeg提取音频轨道                |
| 音频降噪  | 100% | Demucs深度学习降噪                |
| 说话人分离 | 100% | pyannote 3.1                |
| STT转录 | 100% | Faster-Whisper + SenseVoice |
| 韵律分析  | 100% | F0/能量/语速/停顿                 |
| 声音情绪  | 100% | Wav2Vec2分类                  |
| 面部分析  | 100% | MediaPipe 468关键点            |
| AU计算  | 100% | 12+动作单元                     |
| 关键帧提取 | 100% | PySceneDetect               |
| 情绪融合  | 100% | 多模态加权融合                     |
| PDF报告 | 100% | ReportLab中文支持               |
| 声纹识别  | 90%  | 基础功能完成，待优化                  |
| 微表情检测 | 0%   | 待开发                         |

#### 非功能需求完成度

| 需求    | 完成度  | 说明                  |
| ----- | ---- | ------------------- |
| 性能优化  | 80%  | 支持GPU加速，长视频分段处理     |
| 跨平台支持 | 100% | macOS/Linux/Windows |
| 测试覆盖  | 30%  | 基础单元测试，集成测试不足       |
| 文档完善  | 70%  | 技术文档完整，API文档待补充     |
| 错误处理  | 70%  | 基础异常处理，边界情况待完善      |

***

## 五、技术债务与风险

### 5.1 技术债务

| 债务类型      | 位置                   | 影响    | 优先级 |
| --------- | -------------------- | ----- | --- |
| 测试覆盖不足    | tests/               | 回归风险高 | 高   |
| 错误处理不完善   | 多处                   | 用户体验差 | 中   |
| 日志不规范     | src/utils/logging.py | 调试困难  | 中   |
| 配置管理分散    | src/core/config.py   | 维护困难  | 低   |
| 前端类型定义不完整 | frontend/src/types/  | 类型安全差 | 中   |

### 5.2 技术风险

| 风险      | 概率 | 影响 | 缓解措施      |
| ------- | -- | -- | --------- |
| 模型依赖更新  | 中  | 中  | 锁定版本，定期更新 |
| GPU内存不足 | 低  | 高  | 分段处理，模型卸载 |
| 长视频处理超时 | 中  | 中  | 断点续传，进度保存 |
| 并发处理冲突  | 低  | 中  | 数据库锁，任务队列 |

### 5.3 已知问题

| 问题             | 状态    | 解决方案           |
| -------------- | ----- | -------------- |
| PyTorch 2.8兼容性 | ✅ 已解决 | 降级到 2.4.0      |
| NumPy 2.0兼容性   | ✅ 已解决 | 锁定 <2.0        |
| OpenCV版本冲突     | ✅ 已解决 | 锁定 4.9.0.80    |
| Python 3.9类型注解 | ✅ 已解决 | 使用 Optional\[] |

***

## 六、下一步规划

### 6.1 短期目标 (1-2周)

#### P0 - 必须完成

1. **测试覆盖率提升**
   - 目标：单元测试覆盖率 > 60%
   - 重点：核心算法、API路由、数据处理
   - 文件：`tests/unit/`, `tests/integration/`
2. **错误处理完善**
   - 目标：所有API返回标准化错误响应
   - 重点：模型加载失败、文件处理异常、GPU错误
   - 文件：`src/core/exceptions.py`, `src/api/routes/`
3. **API文档补充**
   - 目标：所有API端点有完整文档
   - 重点：请求/响应示例、错误码说明
   - 文件：`docs/api/`

#### P1 - 应该完成

1. **日志规范化**
   - 目标：统一日志格式，支持结构化日志
   - 重点：请求追踪、性能监控、错误堆栈
   - 文件：`src/utils/logging.py`
2. **前端类型定义完善**
   - 目标：所有API响应有TypeScript类型
   - 重点：Interview, Segment, Emotion等核心类型
   - 文件：`frontend/src/types/`

### 6.2 中期目标 (3-4周)

#### P1 - 应该完成

1. **微表情检测 (Phase 9)**
   - 目标：检测100-500ms的快速表情变化
   - 方案：CNN + LSTM时序模型
   - 文件：`src/inference/micro_expression/`
2. **性能优化**
   - 目标：60分钟视频处理 < 20分钟 (GPU)
   - 方案：模型缓存、并行处理、内存优化
   - 文件：`src/services/pipeline/`
3. **用户体验优化**
   - 目标：处理进度实时反馈，错误提示友好
   - 方案：WebSocket推送、错误码国际化
   - 文件：`src/api/routes/`, `frontend/src/components/`

### 6.3 长期目标 (1-2月)

#### P2 - 可以完成

1. **生产环境部署**
   - 目标：Docker化部署，支持Kubernetes
   - 方案：多容器编排、负载均衡、监控告警
   - 文件：`docker/`, `k8s/`
2. **模型优化**
   - 目标：模型量化、推理加速
   - 方案：ONNX导出、TensorRT加速
   - 文件：`src/inference/`
3. **多语言支持**
   - 目标：支持英文、日文等语言
   - 方案：多语言STT模型、情绪模型微调
   - 文件：`src/inference/stt/`, `src/inference/emotion/`

***

## 七、关键决策记录

### 7.1 已做决策

| 决策                 | 原因        | 替代方案           |
| ------------------ | --------- | -------------- |
| 使用SQLite (开发)      | 轻量、零配置    | PostgreSQL     |
| 选择MediaPipe        | 成熟稳定、跨平台  | dlib, OpenCV   |
| 选择pyannote 3.1     | 开源SOTA    | pyannote 2.0   |
| 使用Faster-Whisper   | C++高速推理   | OpenAI Whisper |
| React + Ant Design | 生态丰富、快速开发 | Vue + Element  |

### 7.2 待做决策

| 决策点     | 选项                     | 影响因素   |
| ------- | ---------------------- | ------ |
| 微表情检测方案 | CNN+LSTM / Transformer | 准确率、速度 |
| 生产环境数据库 | PostgreSQL / MySQL     | 并发、成本  |
| 任务队列    | Celery / RQ / Dramatiq | 复杂度、性能 |
| 监控方案    | Prometheus / Grafana   | 可视化、告警 |

***

## 八、质量评估

### 8.1 代码质量评分

| 维度   | 评分     | 说明                |
| ---- | ------ | ----------------- |
| 代码规范 | 75/100 | 使用Ruff检查，部分文件缺少注释 |
| 架构设计 | 85/100 | 分层清晰，模块化良好        |
| 可维护性 | 70/100 | 部分函数过长，耦合度中等      |
| 测试覆盖 | 30/100 | 单元测试不足，集成测试缺失     |
| 文档完善 | 65/100 | 技术文档完整，API文档不足    |

**整体评分**: 65/100 ⭐⭐⭐

### 8.2 改进建议

1. **提升测试覆盖率**
   - 添加单元测试：核心算法、数据处理
   - 添加集成测试：API端到端测试
   - 添加性能测试：处理速度基准
2. **完善错误处理**
   - 统一异常类型
   - 标准化错误响应
   - 友好错误提示
3. **优化代码结构**
   - 拆分过长函数
   - 减少模块耦合
   - 添加类型注解
4. **补充文档**
   - API使用文档
   - 部署文档
   - 开发指南

***

## 九、总结

### 9.1 项目优势

✅ **架构清晰**: 分层设计，模块化良好
✅ **功能完整**: 核心功能已实现，满足基本需求
✅ **技术先进**: 使用SOTA模型，效果优秀
✅ **跨平台**: 支持macOS/Linux/Windows
✅ **可扩展**: 支持模型切换、功能扩展

### 9.2 待改进项

⚠️ **测试不足**: 测试覆盖率低，回归风险高
⚠️ **文档缺失**: API文档不完整，影响使用
⚠️ **性能待优化**: 长视频处理速度可提升
⚠️ **错误处理**: 边界情况处理不完善

### 9.3 下一步行动

1. **立即执行**: 提升测试覆盖率、完善错误处理
2. **近期规划**: 补充API文档、优化性能
3. **中期目标**: 实现微表情检测、生产环境部署

***

**报告完成日期**: 2026-04-02
**下次审查建议**: 2周后
