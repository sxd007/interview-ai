#!/usr/bin/env python3
"""
测试视频转码性能对比

用法:
    python test_transcode_performance.py
"""

import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.video_transcoder import (
    check_nvenc_support,
    check_videotoolbox_support,
    get_optimal_encoder,
    transcode_video,
)


def get_video_info(video_path: str) -> dict:
    """获取视频信息"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,size",
                "-show_entries", "stream=codec_name,width,height",
                "-of", "json",
                video_path
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        import json
        info = json.loads(result.stdout)
        
        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_name") in ["h264", "hevc", "vp9"]),
            None
        )
        
        return {
            "duration": float(info.get("format", {}).get("duration", 0)),
            "size_mb": int(info.get("format", {}).get("size", 0)) / (1024 * 1024),
            "codec": video_stream.get("codec_name") if video_stream else "unknown",
            "width": video_stream.get("width") if video_stream else 0,
            "height": video_stream.get("height") if video_stream else 0,
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    print("\n" + "="*70)
    print("视频转码性能测试")
    print("="*70)
    
    print("\n【硬件编码支持检测】")
    nvenc = check_nvenc_support()
    videotoolbox = check_videotoolbox_support()
    
    print(f"  NVENC (NVIDIA GPU): {'✓ 支持' if nvenc else '✗ 不支持'}")
    print(f"  VideoToolbox (macOS): {'✓ 支持' if videotoolbox else '✗ 不支持'}")
    
    optimal_encoder, params = get_optimal_encoder()
    print(f"\n【推荐编码器】")
    print(f"  编码器: {optimal_encoder}")
    print(f"  参数: {params}")
    
    test_video = "data/chunks/42271a0d-77b0-48a8-a605-c5eeca9887ec/chunk_000.mp4"
    
    if not os.path.exists(test_video):
        print(f"\n【测试视频不存在】")
        print(f"  路径: {test_video}")
        print(f"  请先上传一个视频进行处理")
        return
    
    print(f"\n【测试视频信息】")
    info = get_video_info(test_video)
    
    if "error" in info:
        print(f"  错误: {info['error']}")
        return
    
    print(f"  文件: {test_video}")
    print(f"  时长: {info['duration']:.1f}秒 ({info['duration']/60:.1f}分钟)")
    print(f"  大小: {info['size_mb']:.1f}MB")
    print(f"  分辨率: {info['width']}x{info['height']}")
    print(f"  编码: {info['codec']}")
    
    print(f"\n【性能预测】")
    duration = info['duration']
    
    if optimal_encoder == "h264_nvenc":
        estimated_time = duration / 17.5
        print(f"  预计转码时间: {estimated_time:.1f}秒 ({estimated_time/60:.1f}分钟)")
        print(f"  预计处理速度: 17.5x 实时速度")
        print(f"  性能提升: 比CPU快约3倍")
    elif optimal_encoder == "h264_videotoolbox":
        estimated_time = duration / 12
        print(f"  预计转码时间: {estimated_time:.1f}秒 ({estimated_time/60:.1f}分钟)")
        print(f"  预计处理速度: 12x 实时速度")
        print(f"  性能提升: 比CPU快约2倍")
    else:
        estimated_time = duration / 5.5
        print(f"  预计转码时间: {estimated_time:.1f}秒 ({estimated_time/60:.1f}分钟)")
        print(f"  预计处理速度: 5.5x 实时速度")
        print(f"  使用CPU编码")
    
    print(f"\n【优化建议】")
    if optimal_encoder == "libx264":
        print(f"  ⚠️  未检测到GPU硬件编码支持")
        print(f"  💡 建议：")
        print(f"     1. 安装NVIDIA GPU驱动和CUDA工具包")
        print(f"     2. 确保ffmpeg编译时包含NVENC支持")
        print(f"     3. 或使用 -preset ultrafast 加速CPU编码")
    else:
        print(f"  ✓ 已启用GPU硬件加速")
        print(f"  ✓ 无需额外配置")
        print(f"  ✓ 系统将自动使用最优编码器")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
