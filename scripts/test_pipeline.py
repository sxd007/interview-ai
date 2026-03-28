#!/usr/bin/env python3
"""
Test script for the interview processing pipeline.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.inference.stt.engine import STTEngine
from src.inference.diarization.engine import DiarizationEngine
from src.services.audio.processor import AudioProcessor


def test_stt():
    print("Testing STT Engine...")
    engine = STTEngine(model_size="large-v3-turbo")
    engine.load()
    print("  STT Engine loaded successfully")
    return engine


def test_diarization():
    print("Testing Diarization Engine...")
    token = os.getenv("HF_TOKEN")
    if not token:
        print("  Skipping diarization (no HF_TOKEN)")
        return None
    
    engine = DiarizationEngine(auth_token=token)
    engine.load()
    print("  Diarization Engine loaded successfully")
    return engine


def test_audio_processor():
    print("Testing Audio Processor...")
    processor = AudioProcessor()
    print("  Audio Processor created successfully")
    return processor


def main():
    print("=" * 50)
    print("Interview AI - Processing Pipeline Test")
    print("=" * 50)
    print()

    try:
        stt = test_stt()
        print()
        
        diarization = test_diarization()
        print()
        
        processor = test_audio_processor()
        print()

        print("=" * 50)
        print("All components loaded successfully!")
        print("=" * 50)
        print()
        print("Next steps:")
        print("  1. Upload a video via API")
        print("  2. Start processing: POST /api/interviews/{id}/process")
        print("  3. Get transcript: GET /api/interviews/{id}/transcript")
        
    except Exception as e:
        print()
        print("=" * 50)
        print(f"ERROR: {e}")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
