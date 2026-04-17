#!/usr/bin/env python3
"""
GPU诊断脚本 - 检查GPU是否被正确使用
运行方式: python diagnose_gpu.py
"""

import os
import sys

print("=" * 80)
print("GPU 诊断报告")
print("=" * 80)

print("\n【步骤1】检查PyTorch GPU可用性")
try:
    import torch
    print(f"✓ PyTorch版本: {torch.__version__}")
    print(f"  CUDA可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  CUDA版本: {torch.version.cuda}")
        print(f"  GPU数量: {torch.cuda.device_count()}")
        print(f"  当前GPU: {torch.cuda.current_device()}")
        print(f"  GPU名称: {torch.cuda.get_device_name(0)}")
        print(f"  GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    
    if hasattr(torch.backends, 'mps'):
        print(f"  MPS可用: {torch.backends.mps.is_available()}")
except ImportError as e:
    print(f"✗ PyTorch未安装: {e}")
    sys.exit(1)

print("\n【步骤2】检查环境变量")
env_vars = ['CUDA_VISIBLE_DEVICES', 'CUDA_HOME', 'CUDA_PATH', 'TORCH_HOME']
for var in env_vars:
    value = os.environ.get(var, '未设置')
    print(f"  {var}: {value}")

print("\n【步骤3】检查配置文件")
try:
    from src.core.config import settings
    print(f"✓ 配置加载成功")
    print(f"  device配置: {settings.device}")
    print(f"  GPU可用: {settings.is_gpu_available}")
    print(f"  实际设备: {settings.get_device()}")
except Exception as e:
    print(f"✗ 配置加载失败: {e}")

print("\n【步骤4】检查各引擎的设备检测")
try:
    from src.inference.stt.sensevoice import SenseVoiceEngine
    stt = SenseVoiceEngine(device=None)
    print(f"✓ SenseVoiceEngine")
    print(f"  检测到的设备: {stt.device}")
except Exception as e:
    print(f"✗ SenseVoiceEngine初始化失败: {e}")

try:
    from src.inference.diarization.engine import DiarizationEngine
    diar = DiarizationEngine(auth_token=None)
    print(f"✓ DiarizationEngine")
    print(f"  检测到的设备: {diar.device}")
except Exception as e:
    print(f"✗ DiarizationEngine初始化失败: {e}")

try:
    from src.inference.emotion.engine import VoiceEmotionEngine
    emotion = VoiceEmotionEngine()
    print(f"✓ VoiceEmotionEngine")
    print(f"  检测到的设备: {emotion.device}")
except Exception as e:
    print(f"✗ VoiceEmotionEngine初始化失败: {e}")

try:
    from src.services.audio.processor import AudioProcessor
    audio = AudioProcessor()
    print(f"✓ AudioProcessor")
    print(f"  检测到的设备: {audio.device}")
except Exception as e:
    print(f"✗ AudioProcessor初始化失败: {e}")

print("\n【步骤5】检查FunASR模型加载")
try:
    from funasr import AutoModel
    print("✓ FunASR可用")
    
    # 测试AutoModel的device参数
    test_device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  尝试使用设备: {test_device}")
    
    # 注意: 这里不实际加载模型,只检查参数传递
    print(f"  提示: FunASR AutoModel的device参数应该设置为: {test_device}")
except ImportError:
    print("✗ FunASR未安装")
except Exception as e:
    print(f"✗ FunASR检查失败: {e}")

print("\n" + "=" * 80)
print("诊断建议")
print("=" * 80)

if torch.cuda.is_available():
    print("\n✓ CUDA GPU可用")
    print("\n建议检查:")
    print("1. 确认FunASR模型是否真的加载到了GPU上")
    print("2. 查看处理日志中的设备信息")
    print("3. 使用 nvidia-smi 监控GPU使用情况")
    print("\n快速验证命令:")
    print("  nvidia-smi  # 查看GPU状态")
    print("  watch -n 1 nvidia-smi  # 实时监控GPU使用")
else:
    print("\n✗ CUDA GPU不可用")
    print("\n可能原因:")
    print("1. 没有NVIDIA GPU")
    print("2. NVIDIA驱动未安装或版本不兼容")
    print("3. CUDA工具包未安装")
    print("4. PyTorch未正确安装CUDA版本")
    print("\n解决方法:")
    print("  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")

print("\n" + "=" * 80)
