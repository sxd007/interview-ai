"""
System dependency checker for Interview AI.

This module provides comprehensive system checks for required dependencies
including ffmpeg, GPU availability, and fonts.
"""

import logging
import platform
import shutil
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class SystemChecker:
    """
    Comprehensive system dependency checker.
    
    Checks for required system dependencies and provides helpful
    installation guides for missing components.
    """
    
    @staticmethod
    def check_ffmpeg() -> Tuple[bool, str]:
        """
        Check if ffmpeg is installed.
        
        Returns:
            Tuple of (is_available, message)
        """
        if shutil.which("ffmpeg"):
            try:
                import subprocess
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    text=True
                )
                version_line = result.stdout.split('\n')[0] if result.stdout else "ffmpeg is installed"
                return True, version_line
            except Exception:
                return True, "ffmpeg is installed"
        
        system = platform.system()
        install_guides = {
            "Darwin": "brew install ffmpeg",
            "Linux": "sudo apt install ffmpeg  # Debian/Ubuntu\n  sudo yum install ffmpeg  # CentOS/RHEL",
            "Windows": "choco install ffmpeg  # or download from https://ffmpeg.org/download.html",
        }
        
        guide = install_guides.get(system, "Visit https://ffmpeg.org/download.html")
        return False, f"ffmpeg not found. Install with:\n  {guide}"
    
    @staticmethod
    def check_gpu() -> Dict[str, Any]:
        """
        Check GPU availability (CUDA or MPS).
        
        Returns:
            Dictionary with GPU information
        """
        result = {
            "cuda_available": False,
            "cuda_version": None,
            "gpu_name": None,
            "gpu_count": 0,
            "mps_available": False,
            "platform": platform.system(),
        }
        
        try:
            import torch
            
            result["cuda_available"] = torch.cuda.is_available()
            if result["cuda_available"]:
                result["cuda_version"] = torch.version.cuda
                result["gpu_name"] = torch.cuda.get_device_name(0)
                result["gpu_count"] = torch.cuda.device_count()
            
            if hasattr(torch.backends, 'mps'):
                result["mps_available"] = torch.backends.mps.is_available()
            
        except ImportError:
            logger.warning("PyTorch not installed, cannot check GPU")
        except Exception as e:
            logger.error(f"Error checking GPU: {e}")
        
        return result
    
    @staticmethod
    def check_fonts() -> Dict[str, bool]:
        """
        Check if required fonts are available.
        
        Returns:
            Dictionary indicating availability of each font type
        """
        try:
            from src.utils.fonts import FontManager
            return FontManager.check_fonts_available()
        except ImportError:
            logger.warning("FontManager not available")
            return {"cn_font": False, "unicode_font": False}
    
    @staticmethod
    def check_python_version() -> Tuple[bool, str]:
        """
        Check if Python version meets requirements.
        
        Returns:
            Tuple of (meets_requirements, version_string)
        """
        import sys
        version = sys.version_info
        
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        if version.major == 3 and version.minor >= 9:
            return True, version_str
        
        return False, f"Python {version_str} found, but 3.9+ required"
    
    @staticmethod
    def check_memory() -> Dict[str, Any]:
        """
        Check system memory.
        
        Returns:
            Dictionary with memory information
        """
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_percent": mem.percent,
            }
        except ImportError:
            return {"error": "psutil not installed"}
    
    @classmethod
    def full_check(cls) -> Dict[str, Any]:
        """
        Perform comprehensive system check.
        
        Returns:
            Dictionary with all check results
        """
        ffmpeg_ok, ffmpeg_msg = cls.check_ffmpeg()
        python_ok, python_version = cls.check_python_version()
        
        return {
            "platform": platform.system(),
            "python": {
                "version": python_version,
                "meets_requirements": python_ok,
            },
            "ffmpeg": {
                "available": ffmpeg_ok,
                "message": ffmpeg_msg,
            },
            "gpu": cls.check_gpu(),
            "fonts": cls.check_fonts(),
            "memory": cls.check_memory(),
        }
    
    @classmethod
    def print_report(cls) -> None:
        """Print a formatted system check report."""
        print("\n" + "=" * 60)
        print("System Check Report".center(60))
        print("=" * 60 + "\n")
        
        results = cls.full_check()
        
        print(f"Platform: {results['platform']}")
        print(f"Python: {results['python']['version']}")
        
        if results['python']['meets_requirements']:
            print("  ✓ Python version meets requirements")
        else:
            print("  ✗ Python version does not meet requirements (3.9+ needed)")
        
        print()
        
        if results['ffmpeg']['available']:
            print(f"ffmpeg: ✓ {results['ffmpeg']['message']}")
        else:
            print(f"ffmpeg: ✗ {results['ffmpeg']['message']}")
        
        print()
        
        gpu = results['gpu']
        if gpu['cuda_available']:
            print(f"GPU: ✓ CUDA {gpu['cuda_version']}")
            print(f"  Device: {gpu['gpu_name']}")
            print(f"  Count: {gpu['gpu_count']}")
        elif gpu['mps_available']:
            print("GPU: ✓ MPS (Apple Silicon)")
        else:
            print("GPU: - No GPU available (CPU mode)")
        
        print()
        
        fonts = results['fonts']
        if fonts.get('cn_font'):
            print("Fonts: ✓ Chinese font available")
        else:
            print("Fonts: ✗ Chinese font not found")
            print("  Install with: sudo apt install fonts-noto-cjk (Ubuntu)")
        
        if fonts.get('unicode_font'):
            print("  ✓ Unicode font available")
        else:
            print("  ✗ Unicode font not found")
        
        print()
        print("=" * 60)
        
        all_ok = (
            results['python']['meets_requirements'] and
            results['ffmpeg']['available'] and
            (fonts.get('cn_font') or fonts.get('unicode_font'))
        )
        
        if all_ok:
            print("✓ System ready for Interview AI".center(60))
        else:
            print("⚠ Some dependencies missing".center(60))
        
        print("=" * 60 + "\n")


def check_system() -> Dict[str, Any]:
    """
    Convenience function to perform system check.
    
    Returns:
        Dictionary with all check results
    """
    return SystemChecker.full_check()


def print_system_report() -> None:
    """Print a formatted system check report."""
    SystemChecker.print_report()
