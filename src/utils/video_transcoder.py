"""
视频转码优化工具

支持 GPU 加速的视频转码功能
"""

import os
import subprocess
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def check_nvenc_preset_support() -> str:
    """检查 NVENC 支持的 preset 类型，返回推荐的 preset 值"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-h", "encoder=h264_nvenc"],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout
        
        lines = output.split('\n')
        preset_section = False
        supported_presets = []
        
        for line in lines:
            if '-preset' in line:
                preset_section = True
                continue
            if preset_section and line.strip().startswith('-'):
                break
            if preset_section and line.strip():
                preset_name = line.strip().split()[0]
                if preset_name.isalpha() or preset_name.startswith('p'):
                    supported_presets.append(preset_name)
        
        if 'p4' in supported_presets or 'p1' in supported_presets:
            return "p4"
        elif 'hq' in supported_presets:
            return "hq"
        elif 'medium' in supported_presets:
            return "medium"
        else:
            return "default"
    except Exception as e:
        logger.warning(f"Failed to check NVENC preset support: {e}")
        return "default"


def check_nvenc_support() -> bool:
    """检查系统是否支持 NVIDIA NVENC 硬件编码"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "h264_nvenc" in result.stdout
    except Exception as e:
        logger.warning(f"Failed to check NVENC support: {e}")
        return False


def check_videotoolbox_support() -> bool:
    """检查 macOS 是否支持 VideoToolbox 硬件编码"""
    import platform
    if platform.system() != "Darwin":
        return False
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "h264_videotoolbox" in result.stdout
    except Exception:
        return False


def get_optimal_encoder(force_cpu: bool = False) -> Tuple[str, dict]:
    """
    获取最优的视频编码器
    
    Args:
        force_cpu: 强制使用 CPU 编码（默认 True 以确保稳定性）
    
    Returns:
        (encoder_name, encoder_params): 编码器名称和参数
    """
    if force_cpu:
        logger.info("使用 CPU 软件编码 (libx264) - 稳定模式")
        return "libx264", {
            "preset": "fast",
            "crf": "23",
        }
    
    if check_nvenc_support():
        preset = check_nvenc_preset_support()
        logger.info(f"✓ 使用 NVIDIA NVENC 硬件加速编码 (preset: {preset})")
        return "h264_nvenc", {
            "preset": preset,
            "cq": "23",
        }
    
    if check_videotoolbox_support():
        logger.info("✓ 使用 VideoToolbox 硬件加速编码")
        return "h264_videotoolbox", {
            "q:v": "65",
        }
    
    logger.info("✗ 使用 CPU 软件编码 (libx264)")
    return "libx264", {
        "preset": "fast",
        "crf": "23",
    }


def transcode_video(
    input_path: str,
    output_path: str,
    use_gpu: bool = False,
    preset: Optional[str] = None,
    crf: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    转码视频为 H.264 格式
    
    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        use_gpu: 是否使用 GPU 加速（默认 False 以确保稳定性）
        preset: 编码预设（可选）
        crf: 质量参数（可选）
    
    Returns:
        (success, message): 是否成功和消息
    """
    encoder, encoder_params = get_optimal_encoder(force_cpu=not use_gpu)
    
    if preset:
        encoder_params["preset"] = preset
    if crf:
        if encoder == "h264_nvenc":
            encoder_params["cq"] = str(crf)
        else:
            encoder_params["crf"] = str(crf)
    
    cmd = [
        "ffmpeg",
        "-v", "warning",
        "-y",
        "-i", input_path,
    ]
    
    if encoder == "h264_nvenc":
        cmd.extend([
            "-c:v", encoder,
            "-preset", encoder_params.get("preset", "p4"),
            "-cq", encoder_params.get("cq", "23"),
        ])
    elif encoder == "h264_videotoolbox":
        cmd.extend([
            "-c:v", encoder,
            "-q:v", encoder_params.get("q:v", "65"),
        ])
    else:
        cmd.extend([
            "-c:v", encoder,
            "-preset", encoder_params.get("preset", "fast"),
            "-crf", encoder_params.get("crf", "23"),
        ])
    
    cmd.extend([
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ])
    
    logger.info(f"🎬 开始转码: {input_path}")
    logger.info(f"   编码器: {encoder}")
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


def benchmark_transcode(input_path: str, output_dir: str) -> dict:
    """
    对比不同编码器的性能
    
    Args:
        input_path: 输入视频路径
        output_dir: 输出目录
    
    Returns:
        性能对比结果
    """
    import time
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    
    results = {}
    
    encoders = [
        ("libx264", {"preset": "fast", "crf": "23"}),
        ("libx264", {"preset": "ultrafast", "crf": "23"}),
    ]
    
    if check_nvenc_support():
        encoders.append(("h264_nvenc", {"preset": "p4", "cq": "23"}))
    
    for encoder, params in encoders:
        output_path = os.path.join(
            output_dir,
            f"test_{encoder}_{params.get('preset', 'default')}.mp4"
        )
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试编码器: {encoder} {params}")
        
        start_time = time.time()
        success, msg = transcode_video(
            input_path,
            output_path,
            use_gpu=(encoder != "libx264"),
            **params
        )
        duration = time.time() - start_time
        
        if success:
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            results[f"{encoder}_{params.get('preset', 'default')}"] = {
                "duration": duration,
                "file_size_mb": file_size,
                "success": True,
            }
        else:
            results[f"{encoder}_{params.get('preset', 'default')}"] = {
                "duration": duration,
                "success": False,
                "error": msg,
            }
        
        if os.path.exists(output_path):
            os.remove(output_path)
    
    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("视频转码优化工具")
    print("="*60)
    
    print("\n检查硬件编码支持...")
    print(f"NVENC (NVIDIA): {'✓ 支持' if check_nvenc_support() else '✗ 不支持'}")
    print(f"VideoToolbox (macOS): {'✓ 支持' if check_videotoolbox_support() else '✗ 不支持'}")
    
    print(f"\n推荐编码器: {get_optimal_encoder()[0]}")
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "output.mp4"
        
        print(f"\n转码视频: {input_file} -> {output_file}")
        success, msg = transcode_video(input_file, output_file)
        
        if success:
            print("✓ 转码成功！")
        else:
            print(f"✗ 转码失败: {msg}")
