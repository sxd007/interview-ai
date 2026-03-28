#!/usr/bin/env python3
"""
Pre-download all models to avoid runtime download issues.
Run this once before starting the server, or whenever models need updating.
"""
import os
import sys
import urllib.request

def download_hf_model(repo_id: str, token: str, cache_dir: str = "./models"):
    from huggingface_hub import snapshot_download
    print(f"  Downloading {repo_id}...")
    snapshot_download(repo_id, cache_dir=cache_dir, token=token)
    print(f"  {repo_id} ✓")

def download_mediapipe_model():
    url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    path = os.path.expanduser("~/.cache/mediapipe/face_landmarker.task")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        print(f"  MediaPipe face_landmarker.task already cached ✓")
        return
    print(f"  Downloading MediaPipe face_landmarker.task...")
    urllib.request.urlretrieve(url, path)
    print(f"  MediaPipe face_landmarker.task ✓")

def main():
    print("=" * 50)
    print("Pre-downloading all models")
    print("=" * 50)

    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token or hf_token == "your_huggingface_token_here":
        print("ERROR: Set HF_TOKEN in .env first")
        sys.exit(1)

    cache_dir = "./models"
    os.makedirs(cache_dir, exist_ok=True)

    models = [
        ("FunAudioLLM/SenseVoiceSmall",),
        ("pyannote/segmentation-3.0",),
        ("pyannote/speaker-diarization-3.1",),
        ("mobiuslabsgmbh/faster-whisper-large-v3-turbo",),
    ]

    for args in models:
        repo_id = args[0]
        try:
            download_hf_model(repo_id, hf_token, cache_dir)
        except Exception as e:
            print(f"  FAILED: {e}")

    try:
        download_mediapipe_model()
    except Exception as e:
        print(f"  MediaPipe FAILED: {e}")

    print("\nDemucs models (auto-downloaded on first use):")
    try:
        from demucs.pretrained import get_model
        for name in ["htdemucs_ft", "htdemucs"]:
            try:
                print(f"  Downloading demucs/{name}...")
                get_model(name)
                print(f"  demucs/{name} ✓")
            except Exception as e:
                print(f"  demucs/{name} FAILED: {e}")
    except Exception as e:
        print(f"  Demucs FAILED: {e}")

    print("=" * 50)
    print("Model download complete")
    print("=" * 50)

if __name__ == "__main__":
    main()
