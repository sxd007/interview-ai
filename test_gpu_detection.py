#!/usr/bin/env python3
"""Test GPU availability and device detection."""

import torch
from src.utils.gpu import get_device, get_device_info
from src.inference.stt.sensevoice import SenseVoiceEngine
from src.inference.diarization.engine import DiarizationEngine
from src.inference.emotion.engine import VoiceEmotionEngine
from src.services.audio.processor import AudioProcessor

print("=" * 80)
print("GPU AVAILABILITY TEST")
print("=" * 80)

print("\n1. PyTorch CUDA availability:")
print(f"   torch.cuda.is_available(): {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   torch.cuda.current_device(): {torch.cuda.current_device()}")
    print(f"   torch.cuda.get_device_name(0): {torch.cuda.get_device_name(0)}")
    print(f"   torch.cuda.device_count(): {torch.cuda.device_count()}")

print("\n2. PyTorch MPS availability:")
print(f"   hasattr(torch.backends, 'mps'): {hasattr(torch.backends, 'mps')}")
if hasattr(torch.backends, 'mps'):
    print(f"   torch.backends.mps.is_available(): {torch.backends.mps.is_available()}")

print("\n3. GPU utility get_device():")
device = get_device()
print(f"   Detected device: {device}")

print("\n4. GPU utility get_device_info():")
info = get_device_info()
print(f"   Device info: {info}")

print("\n" + "=" * 80)
print("ENGINE DEVICE DETECTION TEST")
print("=" * 80)

print("\n1. AudioProcessor device:")
audio_proc = AudioProcessor()
print(f"   AudioProcessor.device: {audio_proc.device}")

print("\n2. SenseVoiceEngine device:")
stt_engine = SenseVoiceEngine(device=None)
print(f"   SenseVoiceEngine.device: {stt_engine.device}")

print("\n3. DiarizationEngine device:")
diar_engine = DiarizationEngine(auth_token=None)
print(f"   DiarizationEngine.device: {diar_engine.device}")

print("\n4. VoiceEmotionEngine device:")
emotion_engine = VoiceEmotionEngine()
print(f"   VoiceEmotionEngine.device: {emotion_engine.device}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if torch.cuda.is_available():
    print("\n✓ CUDA GPU is available")
    print(f"  All engines should use: {device}")
    if audio_proc.device == "cuda" and stt_engine.device in ["cuda", "cuda:0"] and diar_engine.device == "cuda" and emotion_engine.device == "cuda":
        print("  ✓ All engines are correctly configured to use CUDA")
    else:
        print("  ✗ Some engines are NOT using CUDA:")
        if audio_proc.device != "cuda":
            print(f"    - AudioProcessor: {audio_proc.device}")
        if stt_engine.device not in ["cuda", "cuda:0"]:
            print(f"    - SenseVoiceEngine: {stt_engine.device}")
        if diar_engine.device != "cuda":
            print(f"    - DiarizationEngine: {diar_engine.device}")
        if emotion_engine.device != "cuda":
            print(f"    - VoiceEmotionEngine: {emotion_engine.device}")
elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
    print("\n✓ MPS (Apple Silicon) GPU is available")
    print(f"  All engines should use: {device}")
else:
    print("\n✗ No GPU available, using CPU")
    print("  This is expected if you don't have a CUDA-capable GPU or Apple Silicon")

print("\n" + "=" * 80)
