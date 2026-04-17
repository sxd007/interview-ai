#!/usr/bin/env python3
"""
验证FunASR是否真的使用了GPU
运行方式: python verify_funasr_gpu.py
"""

import torch
import os

print("=" * 80)
print("FunASR GPU使用验证")
print("=" * 80)

print("\n【步骤1】检查PyTorch CUDA可用性")
print(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU名称: {torch.cuda.get_device_name(0)}")

print("\n【步骤2】创建一个简单的张量测试GPU")
if torch.cuda.is_available():
    x = torch.tensor([1.0, 2.0, 3.0]).cuda()
    print(f"✓ 张量成功创建在GPU上: {x.device}")
else:
    print("✗ CUDA不可用,跳过此测试")

print("\n【步骤3】测试FunASR AutoModel的设备选择")
try:
    from funasr import AutoModel
    
    print("\n测试1: 传入device='cuda'")
    try:
        model1 = AutoModel(
            model="FunAudioLLM/SenseVoiceSmall",
            device="cuda",
            hub="hf",
            trust_remote_code=True,
            disable_update=True,
        )
        print("✓ 模型初始化成功 (device='cuda')")
        
        # 检查模型是否真的在GPU上
        if hasattr(model1, 'model') and hasattr(model1.model, 'device'):
            print(f"  模型设备: {model1.model.device}")
        else:
            print("  ⚠ 无法直接获取模型设备信息")
        
        # 尝试获取模型参数的设备
        try:
            param = next(model1.model.parameters())
            print(f"  模型参数设备: {param.device}")
            if param.device.type == 'cuda':
                print("  ✓ 模型确实在GPU上!")
            else:
                print("  ✗ 模型在CPU上,不是GPU!")
        except Exception as e:
            print(f"  无法获取模型参数: {e}")
        
        del model1
        torch.cuda.empty_cache()
        
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
    
    print("\n测试2: 传入device='cpu'")
    try:
        model2 = AutoModel(
            model="FunAudioLLM/SenseVoiceSmall",
            device="cpu",
            hub="hf",
            trust_remote_code=True,
            disable_update=True,
        )
        print("✓ 模型初始化成功 (device='cpu')")
        
        # 检查模型是否在CPU上
        try:
            param = next(model2.model.parameters())
            print(f"  模型参数设备: {param.device}")
        except Exception as e:
            print(f"  无法获取模型参数: {e}")
        
        del model2
        
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
    
    print("\n测试3: 不传入device参数")
    try:
        model3 = AutoModel(
            model="FunAudioLLM/SenseVoiceSmall",
            hub="hf",
            trust_remote_code=True,
            disable_update=True,
        )
        print("✓ 模型初始化成功 (未指定device)")
        
        # 检查模型自动选择的设备
        try:
            param = next(model3.model.parameters())
            print(f"  模型参数设备: {param.device}")
            if param.device.type == 'cuda':
                print("  ✓ FunASR自动选择了GPU!")
            else:
                print("  ✗ FunASR自动选择了CPU,而不是GPU!")
                print("  ⚠ 这可能是问题所在!")
        except Exception as e:
            print(f"  无法获取模型参数: {e}")
        
        del model3
        torch.cuda.empty_cache()
        
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
    
except ImportError:
    print("✗ FunASR未安装")
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("结论")
print("=" * 80)
print("\n如果FunASR在没有指定device时自动选择CPU,")
print("那么我们需要在代码中显式指定device='cuda'")
print("\n建议修改:")
print("  在 src/inference/stt/sensevoice.py 的 load() 方法中,")
print("  确保传给AutoModel的device参数是'cuda'而不是None")
print("=" * 80)
