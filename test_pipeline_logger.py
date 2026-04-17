"""
测试Pipeline日志系统

这个脚本用于验证日志追踪系统是否正常工作。
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

log_file = "test_pipeline.log"

handlers = [logging.StreamHandler(sys.stdout)]
handlers.append(logging.FileHandler(log_file, mode='w'))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=handlers,
)

from src.utils.pipeline_logger import get_pipeline_logger, pipeline_context, PipelineLogger

def test_basic_logging():
    """测试基本日志功能"""
    print("\n" + "="*80)
    print("测试1: 基本日志功能")
    print("="*80)
    
    logger = get_pipeline_logger("test")
    
    logger.log_stage_start("test_stage", "测试阶段", device="cpu")
    logger.log_progress(50, 100, "处理中")
    logger.log_stage_end("test_stage", "测试阶段", 1.5, success=True)


def test_device_info():
    """测试设备信息获取"""
    print("\n" + "="*80)
    print("测试2: 设备信息获取")
    print("="*80)
    
    device_info = PipelineLogger.get_device_info()
    print(f"设备类型: {device_info['device']}")
    print(f"设备名称: {device_info['device_name']}")
    print(f"CUDA可用: {device_info['cuda_available']}")
    print(f"MPS可用: {device_info['mps_available']}")


def test_context_manager():
    """测试上下文管理器"""
    print("\n" + "="*80)
    print("测试3: 上下文管理器")
    print("="*80)
    
    import time
    
    with pipeline_context("context_test", "上下文测试", device="cpu"):
        print("执行一些操作...")
        time.sleep(0.5)


def test_format_functions():
    """测试格式化函数"""
    print("\n" + "="*80)
    print("测试4: 格式化函数")
    print("="*80)
    
    logger = get_pipeline_logger("test")
    
    print(f"0.5秒 -> {logger.format_duration(0.5)}")
    print(f"5.0秒 -> {logger.format_duration(5.0)}")
    print(f"125.5秒 -> {logger.format_duration(125.5)}")
    
    print(f"512MB -> {logger.format_memory(512)}")
    print(f"2048MB -> {logger.format_memory(2048)}")


def test_model_logging():
    """测试模型加载/卸载日志"""
    print("\n" + "="*80)
    print("测试5: 模型日志")
    print("="*80)
    
    logger = get_pipeline_logger("test")
    
    logger.log_model_load("test-model", "cuda", "1.5GB")
    logger.log_model_unload("test-model", "cuda")


def test_device_switch():
    """测试设备切换日志"""
    print("\n" + "="*80)
    print("测试6: 设备切换")
    print("="*80)
    
    logger = get_pipeline_logger("test")
    
    logger.log_device_switch("cpu", "cuda", "GPU加速")
    logger.log_device_switch("cuda", "cpu", "内存不足")


if __name__ == "__main__":
    import logging
    
    log_file = "test_pipeline.log"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    handlers.append(logging.FileHandler(log_file, mode='w'))
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    
    print("\n" + "🚀 开始测试Pipeline日志系统")
    print("="*80)
    
    test_basic_logging()
    test_device_info()
    test_context_manager()
    test_format_functions()
    test_model_logging()
    test_device_switch()
    
    print("\n" + "="*80)
    print("✅ 所有测试完成！")
    print("="*80)
    print(f"\n日志已保存到: {log_file}")
