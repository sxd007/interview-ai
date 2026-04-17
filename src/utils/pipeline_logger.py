"""
Pipeline日志追踪模块

提供统一的日志追踪功能，用于记录pipeline各个节点的执行时间、设备信息等。
"""

import time
import functools
from typing import Optional, Callable, Any, Dict
from contextlib import contextmanager
from datetime import datetime
import logging

import torch


class PipelineLogger:
    """Pipeline日志追踪器"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._indent_level = 0
        self._indent_str = "  "
    
    def _get_indent(self) -> str:
        return self._indent_str * self._indent_level
    
    def _log_with_indent(self, level: int, message: str):
        indent = self._get_indent()
        formatted_msg = f"{indent}{message}"
        if level == logging.INFO:
            self.logger.info(formatted_msg)
        elif level == logging.WARNING:
            self.logger.warning(formatted_msg)
        elif level == logging.ERROR:
            self.logger.error(formatted_msg)
        elif level == logging.DEBUG:
            self.logger.debug(formatted_msg)
    
    @staticmethod
    def get_device_info() -> Dict[str, Any]:
        """获取当前设备信息"""
        device_info = {
            "device": "cpu",
            "device_name": "CPU",
            "cuda_available": torch.cuda.is_available(),
            "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
        }
        
        if torch.cuda.is_available():
            device_info["device"] = "cuda"
            device_info["device_name"] = torch.cuda.get_device_name(0)
            device_info["cuda_memory_allocated"] = torch.cuda.memory_allocated(0) / 1024**2
            device_info["cuda_memory_reserved"] = torch.cuda.memory_reserved(0) / 1024**2
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device_info["device"] = "mps"
            device_info["device_name"] = "Apple Silicon GPU"
        
        return device_info
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化持续时间"""
        if seconds < 1:
            return f"{seconds * 1000:.2f}ms"
        elif seconds < 60:
            return f"{seconds:.2f}s"
        else:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.2f}s"
    
    @staticmethod
    def format_memory(mb: float) -> str:
        """格式化内存大小"""
        if mb < 1024:
            return f"{mb:.2f}MB"
        else:
            return f"{mb / 1024:.2f}GB"
    
    def log_stage_start(
        self,
        stage_name: str,
        stage_label: str,
        device: Optional[str] = None,
        extra_info: Optional[Dict[str, Any]] = None,
    ):
        """记录阶段开始"""
        device_info = self.get_device_info()
        device_str = device or device_info["device"]
        
        msg_parts = [
            f"{'='*60}",
            f"🚀 [{stage_name}] {stage_label} - 开始执行",
            f"📍 设备: {device_info['device_name']} ({device_str})",
        ]
        
        if device_info["device"] == "cuda":
            msg_parts.append(
                f"💾 GPU内存: 已分配 {self.format_memory(device_info['cuda_memory_allocated'])} | "
                f"已保留 {self.format_memory(device_info['cuda_memory_reserved'])}"
            )
        
        if extra_info:
            for key, value in extra_info.items():
                msg_parts.append(f"   {key}: {value}")
        
        msg_parts.append(f"{'='*60}")
        
        for line in msg_parts:
            self._log_with_indent(logging.INFO, line)
        
        self._indent_level += 1
    
    def log_stage_end(
        self,
        stage_name: str,
        stage_label: str,
        duration: float,
        success: bool = True,
        extra_info: Optional[Dict[str, Any]] = None,
    ):
        """记录阶段结束"""
        self._indent_level = max(0, self._indent_level - 1)
        
        device_info = self.get_device_info()
        
        status_emoji = "✅" if success else "❌"
        status_text = "成功完成" if success else "执行失败"
        
        msg_parts = [
            f"{'='*60}",
            f"{status_emoji} [{stage_name}] {stage_label} - {status_text}",
            f"⏱️  耗时: {self.format_duration(duration)}",
        ]
        
        if device_info["device"] == "cuda":
            msg_parts.append(
                f"💾 GPU内存: 已分配 {self.format_memory(device_info['cuda_memory_allocated'])} | "
                f"已保留 {self.format_memory(device_info['cuda_memory_reserved'])}"
            )
        
        if extra_info:
            for key, value in extra_info.items():
                msg_parts.append(f"   {key}: {value}")
        
        msg_parts.append(f"{'='*60}")
        
        for line in msg_parts:
            self._log_with_indent(logging.INFO, line)
    
    def log_device_switch(self, from_device: str, to_device: str, reason: str = ""):
        """记录设备切换"""
        msg = f"🔄 设备切换: {from_device.upper()} → {to_device.upper()}"
        if reason:
            msg += f" ({reason})"
        self._log_with_indent(logging.INFO, msg)
    
    def log_progress(self, current: int, total: int, message: str = ""):
        """记录进度"""
        percentage = (current / total * 100) if total > 0 else 0
        msg = f"📊 进度: {current}/{total} ({percentage:.1f}%)"
        if message:
            msg += f" - {message}"
        self._log_with_indent(logging.INFO, msg)
    
    def log_model_load(self, model_name: str, device: str, model_size: Optional[str] = None):
        """记录模型加载"""
        msg = f"📦 加载模型: {model_name}"
        if model_size:
            msg += f" (大小: {model_size})"
        msg += f" → 设备: {device.upper()}"
        self._log_with_indent(logging.INFO, msg)
    
    def log_model_unload(self, model_name: str, device: str):
        """记录模型卸载"""
        msg = f"📤 卸载模型: {model_name} (设备: {device.upper()})"
        self._log_with_indent(logging.INFO, msg)


def pipeline_stage(
    stage_name: str,
    stage_label: str,
    device: Optional[str] = None,
):
    """
    装饰器：自动记录pipeline阶段的执行
    
    Args:
        stage_name: 阶段名称（英文标识）
        stage_label: 阶段标签（中文描述）
        device: 指定设备（可选，自动检测）
    
    Example:
        @pipeline_stage("audio_extract", "音频提取", device="cpu")
        def extract_audio(video_path: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = PipelineLogger(func.__module__)
            
            logger.log_stage_start(stage_name, stage_label, device)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.log_stage_end(stage_name, stage_label, duration, success=True)
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.log_stage_end(
                    stage_name, stage_label, duration,
                    success=False,
                    extra_info={"错误": str(e)}
                )
                raise
        
        return wrapper
    return decorator


@contextmanager
def pipeline_context(
    stage_name: str,
    stage_label: str,
    device: Optional[str] = None,
    logger: Optional[PipelineLogger] = None,
):
    """
    上下文管理器：记录代码块的执行
    
    Args:
        stage_name: 阶段名称
        stage_label: 阶段标签
        device: 设备信息
        logger: 日志记录器（可选）
    
    Example:
        with pipeline_context("stt", "语音转文字", device="cuda"):
            result = stt_engine.transcribe(audio_path)
    """
    if logger is None:
        logger = PipelineLogger("pipeline")
    
    logger.log_stage_start(stage_name, stage_label, device)
    start_time = time.time()
    
    try:
        yield
        duration = time.time() - start_time
        logger.log_stage_end(stage_name, stage_label, duration, success=True)
    except Exception as e:
        duration = time.time() - start_time
        logger.log_stage_end(
            stage_name, stage_label, duration,
            success=False,
            extra_info={"错误": str(e)}
        )
        raise


def get_pipeline_logger(name: str) -> PipelineLogger:
    """获取Pipeline日志记录器"""
    return PipelineLogger(name)
