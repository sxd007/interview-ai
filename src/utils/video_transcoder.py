"""
视频转码优化工具

使用 NVIDIA NVENC GPU 加速编码
"""

import os
import subprocess
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

NVENC_PRESET = "hq"
NVENC_CQ = "23"


def get_optimal_encoder() -> Tuple[str, dict]:
    """
    获取视频编码器配置
    
    Returns:
        (encoder_name, encoder_params): 编码器名称和参数
    """
    logger.info(f"✓ 使用 NVIDIA NVENC GPU 硬件加速编码 (preset: {NVENC_PRESET})")
    return "h264_nvenc", {
        "preset": NVENC_PRESET,
        "cq": NVENC_CQ,
    }


def transcode_video(
    input_path: str,
    output_path: str,
    preset: Optional[str] = None,
    cq: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    使用 GPU 加速转码视频为 H.264 格式
    
    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        preset: 编码预设（可选，默认 hq）
        cq: 质量参数（可选，默认 23）
    
    Returns:
        (success, message): 是否成功和消息
    """
    encoder, encoder_params = get_optimal_encoder()
    
    if preset:
        encoder_params["preset"] = preset
    if cq:
        encoder_params["cq"] = str(cq)
    
    cmd = [
        "ffmpeg",
        "-v", "warning",
        "-y",
        "-i", input_path,
        "-c:v", "h264_nvenc",
        "-preset", encoder_params.get("preset", NVENC_PRESET),
        "-cq", encoder_params.get("cq", NVENC_CQ),
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    
    logger.info(f"🎬 开始 GPU 转码: {input_path}")
    logger.info(f"   编码器: h264_nvenc")
    logger.info(f"   参数: {encoder_params}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            logger.error(f"转码失败: {error_msg}")
            if os.path.exists(output_path):
                os.remove(output_path)
                logger.info(f"已清理失败的输出文件: {output_path}")
            return False, error_msg
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            error_msg = "转码输出文件为空或不存在"
            logger.error(error_msg)
            return False, error_msg
        
        logger.info(f"✓ 转码完成: {output_path}")
        return True, "Success"
        
    except subprocess.TimeoutExpired:
        error_msg = "转码超时（超过1小时）"
        logger.error(error_msg)
        if os.path.exists(output_path):
            os.remove(output_path)
        return False, error_msg
    except Exception as e:
        error_msg = f"转码异常: {str(e)}"
        logger.error(error_msg)
        if os.path.exists(output_path):
            os.remove(output_path)
        return False, error_msg


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("视频转码工具 (GPU NVENC)")
    print("="*60)
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "output.mp4"
        
        print(f"\n转码视频: {input_file} -> {output_file}")
        success, msg = transcode_video(input_file, output_file)
        
        if success:
            print("✓ 转码成功！")
        else:
            print(f"✗ 转码失败: {msg}")
