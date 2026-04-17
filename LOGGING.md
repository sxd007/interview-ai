# Pipeline 日志系统使用指南

## 📝 日志配置

### 日志文件位置
所有应用日志都输出到 `logs/app.log` 文件，包括：
- API 请求日志
- Pipeline 处理日志
- 模型加载/卸载日志
- 设备切换日志
- 错误和警告信息

### 日志轮转
- 单个日志文件最大 50MB
- 保留最近 5 个日志文件
- 自动轮转，无需手动清理

## 🚀 启动应用

### 方式1: 标准启动（推荐）
```bash
uvicorn src.api.main:app --reload --log-level debug
```

日志会同时输出到：
- **控制台**: 实时查看
- **logs/app.log**: 持久化存储

### 方式2: 后台启动
```bash
nohup uvicorn src.api.main:app --log-level debug > /dev/null 2>&1 &
```

日志仍然会写入 `logs/app.log` 文件。

## 📊 查看日志

### 实时查看日志（推荐）
```bash
python tail_log.py --follow
```

或使用简写：
```bash
python tail_log.py -f
```

### 查看最近N行
```bash
# 查看最近50行（默认）
python tail_log.py

# 查看最近100行
python tail_log.py --lines 100
# 或
python tail_log.py -n 100
```

### 使用系统命令
```bash
# 实时跟踪
tail -f logs/app.log

# 查看最后100行
tail -n 100 logs/app.log

# 搜索特定内容
grep "ERROR" logs/app.log
grep "GPU" logs/app.log
```

## 📋 日志内容示例

### Pipeline 阶段日志
```
============================================================
🚀 [audio_extract] 音频提取 - 开始执行
📍 设备: CPU (cpu)
============================================================
✅ [audio_extract] 音频提取 - 成功完成
⏱️  耗时: 1.50s
============================================================

============================================================
🚀 [diarization] 人声识别 - 开始执行
📍 设备: NVIDIA GeForce RTX 3090 (cuda)
💾 GPU内存: 已分配 2.50GB | 已保留 4.00GB
============================================================
✅ [diarization] 人声识别 - 成功完成
⏱️  耗时: 5.23s
   识别到的说话人数量: 2
   音频片段数量: 45
============================================================
```

### 模型加载日志
```
📦 加载模型: SenseVoiceSmall → 设备: CUDA
📤 卸载模型: SenseVoiceSmall (设备: CUDA)
```

### 设备切换日志
```
🔄 设备切换: CPU → CUDA (GPU加速)
🔄 设备切换: CUDA → CPU (内存不足)
```

## 🔍 日志级别

在 `.env` 文件中设置：
```bash
LOG_LEVEL=DEBUG  # 详细调试信息
LOG_LEVEL=INFO   # 常规信息（推荐）
LOG_LEVEL=WARNING # 仅警告和错误
LOG_LEVEL=ERROR  # 仅错误信息
```

## 📈 性能监控

### 查看处理耗时
```bash
grep "耗时" logs/app.log
```

### 查看GPU使用情况
```bash
grep "GPU内存" logs/app.log
```

### 查看错误信息
```bash
grep "ERROR\|FAILED" logs/app.log
```

## 🛠️ 故障排查

### 问题：日志文件不存在
**解决方案**：应用启动时会自动创建 `logs/` 目录和日志文件

### 问题：日志文件过大
**解决方案**：日志会自动轮转，每个文件最大 50MB，保留 5 个备份

### 问题：看不到详细日志
**解决方案**：
1. 检查 `.env` 中的 `LOG_LEVEL` 设置
2. 确保使用 `--log-level debug` 启动 uvicorn
3. 查看 `logs/app.log` 文件而不是控制台输出

## 💡 最佳实践

1. **开发环境**: 使用 `--log-level debug` 查看详细信息
2. **生产环境**: 使用 `--log-level info` 减少日志量
3. **定期检查**: 使用 `tail -f logs/app.log` 监控运行状态
4. **问题排查**: 使用 `grep` 搜索关键错误信息

## 📚 相关文件

- 日志配置: `src/utils/logging.py`
- Pipeline日志: `src/utils/pipeline_logger.py`
- 应用入口: `src/api/main.py`
- 日志查看: `tail_log.py`
