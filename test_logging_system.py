"""
测试日志系统是否正常工作
"""

import sys
import os
import logging
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.logging import setup_logging
from src.utils.pipeline_logger import get_pipeline_logger, pipeline_context

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "app.log"

print(f"日志文件: {log_file.absolute()}")

setup_logging(level="DEBUG", log_file=str(log_file))

logger = get_pipeline_logger("test")

print("\n" + "="*80)
print("开始测试日志系统")
print("="*80)

logger.log_stage_start("test_stage", "测试阶段", device="cpu")
logger.log_progress(50, 100, "处理中")
logger.log_model_load("test-model", "cuda", "1.5GB")
logger.log_device_switch("cpu", "cuda", "GPU加速")
logger.log_stage_end("test_stage", "测试阶段", 2.5, success=True)

with pipeline_context("context_test", "上下文测试", device="cpu"):
    import time
    time.sleep(0.5)

logging.shutdown()

print("\n" + "="*80)
print("✅ 测试完成！")
print("="*80)
print(f"\n请查看日志文件: {log_file.absolute()}")
print(f"或运行: cat {log_file}")
