"""
Cross-platform font management for PDF generation.

This module provides platform-aware font detection and registration for ReportLab,
supporting macOS, Linux, and Windows with automatic fallback mechanisms.
"""

import logging
import os
import platform
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FontManager:
    """
    Manages font registration across different platforms.
    
    Provides automatic platform detection and font path resolution with
    fallback support for missing fonts.
    """
    
    FONT_REGISTRY: Dict[str, Dict[str, str]] = {
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
    
    FALLBACK_FONTS: Dict[str, List[str]] = {
        "cn_font": [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        ],
        "unicode_font": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ],
    }
    
    _registered: bool = False
    _registration_results: Dict[str, bool] = {}
    
    @classmethod
    def get_font_path(cls, font_type: str) -> Optional[str]:
        """
        Get the appropriate font path for the current platform.
        
        Args:
            font_type: Type of font ('cn_font' or 'unicode_font')
            
        Returns:
            Font path if found, None otherwise
        """
        system = platform.system()
        registry = cls.FONT_REGISTRY.get(system, cls.FONT_REGISTRY["Linux"])
        
        primary_path = registry.get(font_type)
        if primary_path and os.path.exists(primary_path):
            logger.debug(f"Found primary {font_type}: {primary_path}")
            return primary_path
        
        logger.debug(f"Primary {font_type} not found at {primary_path}, trying fallbacks")
        
        for fallback in cls.FALLBACK_FONTS.get(font_type, []):
            if os.path.exists(fallback):
                logger.debug(f"Found fallback {font_type}: {fallback}")
                return fallback
        
        logger.warning(f"No {font_type} found on system")
        return None
    
    @classmethod
    def register_fonts(cls) -> Dict[str, bool]:
        """
        Register fonts with ReportLab.
        
        Returns:
            Dictionary mapping font types to registration success status
        """
        if cls._registered:
            logger.debug("Fonts already registered, returning cached results")
            return cls._registration_results
        
        logger.info(f"Registering fonts for platform: {platform.system()}")
        
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError as e:
            logger.error(f"ReportLab not installed: {e}")
            return {"cn_font": False, "unicode_font": False}
        
        results = {}
        
        cn_path = cls.get_font_path("cn_font")
        if cn_path:
            try:
                pdfmetrics.registerFont(TTFont("CN", cn_path))
                results["cn_font"] = True
                logger.info(f"Registered Chinese font: {cn_path}")
            except Exception as e:
                logger.error(f"Failed to register Chinese font: {e}")
                results["cn_font"] = False
        else:
            logger.warning(
                "Chinese font not found. PDF generation may fail. "
                "Install with: sudo apt install fonts-noto-cjk (Ubuntu) "
                "or the font should be available on macOS"
            )
            results["cn_font"] = False
        
        unicode_path = cls.get_font_path("unicode_font")
        if unicode_path:
            try:
                pdfmetrics.registerFont(TTFont("ArialUnicode", unicode_path))
                results["unicode_font"] = True
                logger.info(f"Registered Unicode font: {unicode_path}")
            except Exception as e:
                logger.error(f"Failed to register Unicode font: {e}")
                results["unicode_font"] = False
        else:
            logger.warning(
                "Unicode font not found. PDF generation may have issues. "
                "Install with: sudo apt install fonts-dejavu-core (Ubuntu)"
            )
            results["unicode_font"] = False
        
        cls._registered = True
        cls._registration_results = results
        
        return results
    
    @classmethod
    def get_available_fonts(cls) -> Dict[str, List[str]]:
        """
        Get list of available fonts on the system.
        
        Returns:
            Dictionary mapping font types to list of available paths
        """
        available = {"cn_font": [], "unicode_font": []}
        
        for font_type in ["cn_font", "unicode_font"]:
            primary = cls.FONT_REGISTRY.get(platform.system(), {}).get(font_type)
            if primary and os.path.exists(primary):
                available[font_type].append(primary)
            
            for fallback in cls.FALLBACK_FONTS.get(font_type, []):
                if os.path.exists(fallback) and fallback not in available[font_type]:
                    available[font_type].append(fallback)
        
        return available
    
    @classmethod
    def check_fonts_available(cls) -> Dict[str, bool]:
        """
        Check if required fonts are available.
        
        Returns:
            Dictionary indicating availability of each font type
        """
        return {
            "cn_font": cls.get_font_path("cn_font") is not None,
            "unicode_font": cls.get_font_path("unicode_font") is not None,
        }
    
    @classmethod
    def get_installation_guide(cls) -> str:
        """
        Get platform-specific font installation guide.
        
        Returns:
            Installation instructions string
        """
        system = platform.system()
        
        if system == "Darwin":
            return (
                "macOS should have built-in Chinese fonts.\n"
                "If fonts are missing, install them from Font Book app."
            )
        elif system == "Linux":
            return (
                "Install Chinese fonts:\n"
                "  Ubuntu/Debian: sudo apt install fonts-noto-cjk\n"
                "  CentOS/RHEL:   sudo yum install google-noto-sans-cjk-fonts\n"
                "  Arch Linux:    sudo pacman -S noto-fonts-cjk\n\n"
                "Install Unicode fonts:\n"
                "  Ubuntu/Debian: sudo apt install fonts-dejavu-core\n"
                "  CentOS/RHEL:   sudo yum install dejavu-sans-fonts\n"
                "  Arch Linux:    sudo pacman -S ttf-dejavu"
            )
        elif system == "Windows":
            return (
                "Windows should have built-in Chinese fonts (Microsoft YaHei).\n"
                "If fonts are missing, install them from Windows Settings."
            )
        else:
            return (
                "Please install Chinese and Unicode fonts for your platform.\n"
                "Recommended fonts:\n"
                "  - Noto Sans CJK (Chinese)\n"
                "  - DejaVu Sans (Unicode)"
            )


def get_font_manager() -> FontManager:
    """Get the FontManager class (for consistency with other modules)."""
    return FontManager


def register_fonts() -> Dict[str, bool]:
    """
    Convenience function to register fonts.
    
    Returns:
        Dictionary mapping font types to registration success status
    """
    return FontManager.register_fonts()
