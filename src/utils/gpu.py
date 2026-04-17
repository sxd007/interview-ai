"""
GPU device management utilities.

This module provides unified GPU device selection and memory management
across different platforms (CUDA, MPS, CPU).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_device(device: Optional[str] = None) -> str:
    """
    Get the appropriate device for computation.
    
    Args:
        device: Device preference ('auto', 'cuda', 'mps', 'cpu', or specific like 'cuda:0')
        
    Returns:
        Device string ('cuda', 'mps', or 'cpu')
    """
    logger.info("[GPU] 开始检测GPU设备...")
    
    if device and device != "auto":
        logger.info(f"[GPU] 使用指定的设备配置: {device}")
        return device
    
    try:
        import torch
        
        logger.info(f"[GPU] PyTorch版本: {torch.__version__}")
        
        if torch.cuda.is_available():
            device_name = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            gpu_count = torch.cuda.device_count()
            cuda_version = torch.version.cuda
            
            logger.info(f"[GPU] ✓ CUDA可用")
            logger.info(f"[GPU]   CUDA版本: {cuda_version}")
            logger.info(f"[GPU]   GPU数量: {gpu_count}")
            logger.info(f"[GPU]   GPU名称: {gpu_name}")
            logger.info(f"[GPU]   GPU内存: {gpu_memory:.2f} GB")
            logger.info(f"[GPU] ✓ 最终选择设备: {device_name}")
            
            return device_name
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device_name = "mps"
            logger.info("[GPU] ✓ MPS可用 (Apple Silicon)")
            logger.info(f"[GPU] ✓ 最终选择设备: {device_name}")
            return device_name
        else:
            logger.info("[GPU] ✗ CUDA不可用")
            logger.info("[GPU] ✗ MPS不可用")
            logger.info("[GPU] ✓ 最终选择设备: cpu")
            return "cpu"
            
    except ImportError:
        logger.warning("[GPU] ✗ PyTorch未安装，使用CPU")
        logger.info("[GPU] ✓ 最终选择设备: cpu")
        return "cpu"


def clear_memory(device: str) -> None:
    """
    Clear GPU memory for the specified device.
    
    Args:
        device: Device to clear memory for ('cuda', 'mps', or 'cpu')
    """
    try:
        import torch
        
        if device.startswith("cuda"):
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.debug("Cleared CUDA memory")
        elif device == "mps":
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                torch.mps.empty_cache()
                logger.debug("Cleared MPS memory")
        else:
            import gc
            gc.collect()
            logger.debug("Ran garbage collection for CPU")
            
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Error clearing memory for device {device}: {e}")


def get_device_info() -> dict:
    """
    Get detailed information about available devices.
    
    Returns:
        Dictionary with device information
    """
    info = {
        "cuda": {"available": False, "devices": []},
        "mps": {"available": False},
        "cpu": {"available": True},
    }
    
    try:
        import torch
        
        if torch.cuda.is_available():
            info["cuda"]["available"] = True
            info["cuda"]["version"] = torch.version.cuda
            info["cuda"]["device_count"] = torch.cuda.device_count()
            info["cuda"]["devices"] = [
                {
                    "index": i,
                    "name": torch.cuda.get_device_name(i),
                    "memory_gb": round(torch.cuda.get_device_properties(i).total_memory / (1024**3), 2),
                }
                for i in range(torch.cuda.device_count())
            ]
        
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            info["mps"]["available"] = True
        
    except ImportError:
        pass
    
    return info


def get_memory_usage(device: str) -> dict:
    """
    Get memory usage for the specified device.
    
    Args:
        device: Device to check memory for
        
    Returns:
        Dictionary with memory information
    """
    result = {"device": device, "available": False}
    
    try:
        import torch
        
        if device.startswith("cuda") and torch.cuda.is_available():
            result["available"] = True
            result["allocated_gb"] = round(torch.cuda.memory_allocated() / (1024**3), 3)
            result["cached_gb"] = round(torch.cuda.memory_reserved() / (1024**3), 3)
            result["max_allocated_gb"] = round(torch.cuda.max_memory_allocated() / (1024**3), 3)
        elif device == "mps" and hasattr(torch.backends, 'mps'):
            result["available"] = True
            result["note"] = "MPS does not provide detailed memory stats"
        else:
            import psutil
            result["available"] = True
            mem = psutil.virtual_memory()
            result["total_gb"] = round(mem.total / (1024**3), 2)
            result["available_gb"] = round(mem.available / (1024**3), 2)
            result["used_percent"] = mem.percent
            
    except ImportError:
        pass
    except Exception as e:
        result["error"] = str(e)
    
    return result


class DeviceManager:
    """
    Context manager for GPU device management.
    
    Automatically handles device selection and memory cleanup.
    """
    
    def __init__(self, device: Optional[str] = None):
        """
        Initialize device manager.
        
        Args:
            device: Device preference (None for auto-detect)
        """
        self.device = get_device(device)
        self._original_device = None
    
    def __enter__(self):
        """Enter context and set device."""
        import torch
        
        self._original_device = torch.cuda.current_device() if torch.cuda.is_available() else None
        
        if self.device.startswith("cuda"):
            device_idx = int(self.device.split(":")[1]) if ":" in self.device else 0
            torch.cuda.set_device(device_idx)
        
        return self.device
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and clean up memory."""
        clear_memory(self.device)
        
        if self._original_device is not None:
            import torch
            torch.cuda.set_device(self._original_device)
        
        return False
