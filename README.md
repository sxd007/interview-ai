# Interview AI - Interview Video Intelligence System

Multi-modal analysis system for psychological research and compliance investigation interviews.

## Features

- **Audio Processing**: STT (Speech-to-Text), speaker diarization, denoising, prosody analysis
- **Video Analysis**: Face detection, action units (AU), emotion recognition
- **Psychological Analysis**: Stress signals, avoidance detection, confidence assessment
- **Multi-modal Fusion**: Combined audio + video emotion analysis
- **Timeline Visualization**: Synchronized playback with emotion curves
- **Chunk Processing**: Process long videos in parallel chunks for faster analysis
- **Cross-platform Support**: Runs on macOS (M1/M2/M3), Linux (CPU/GPU)

## Quick Start

### Prerequisites

- Python 3.9+
- FFmpeg
- For GPU acceleration: NVIDIA GPU + CUDA 12.1+ (optional)

### Installation

#### 1. Clone the repository

```bash
git clone https://github.com/sxd007/interview-ai.git
cd interview-ai
```

#### 2. Install dependencies

**Using Poetry (recommended)**:

```bash
poetry install
```

**Using pip**:

```bash
pip install -r requirements.txt
```

#### 3. Set environment variables

```bash
cp .env.example .env
# Edit .env and add your HuggingFace token
# Get token from: https://huggingface.co/settings/tokens
```

#### 4. Start the application

**Local development**:

```bash
# Backend
poetry run uvicorn src.api.main:app --reload

# Frontend (in another terminal)
cd frontend && npm install && npm run dev
```

**Using Docker**:

CPU version (macOS / Linux without GPU):

```bash
cd docker
docker-compose up api-cpu
```

GPU version (Linux with NVIDIA GPU):

```bash
cd docker
docker-compose up api-gpu
```

## Configuration

Key environment variables:

| Variable          | Description                        | Default                            |
| ----------------- | ---------------------------------- | ---------------------------------- |
| `HF_TOKEN`        | HuggingFace token for model access | -                                  |
| `DATABASE_URL`    | Database connection string         | `sqlite:///./data/interview_ai.db` |
| `MODEL_CACHE_DIR` | Directory for cached models        | `./models`                         |
| `device`          | Compute device: auto/cpu/cuda/mps  | `auto`                             |

## Project Structure

```
interview-ai/
├── src/
│   ├── api/              # FastAPI routes and schemas
│   ├── core/             # Configuration and utilities
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   │   ├── audio/       # Audio processing
│   │   ├── video/       # Video analysis
│   │   └── emotion/     # Emotion analysis
│   ├── inference/       # Model inference
│   │   ├── stt/         # Speech-to-text
│   │   ├── diarization/ # Speaker diarization
│   │   ├── face/        # Face detection
│   │   └── emotion/     # Emotion recognition
│   └── utils/            # Utilities
├── frontend/             # React + TypeScript frontend
├── docker/               # Docker configurations
├── scripts/             # Utility scripts
└── tests/               # Test suite
```

## API Documentation

Once running, visit:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, PyTorch
- **Frontend**: React, TypeScript, Ant Design
- **ML Models**:
  - FunASR (Speech-to-Text)
  - pyannote (Speaker Diarization)
  - Transformers (Emotion Recognition)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributors

- sxd007
- OpenCode AI Assistant

## Acknowledgments

- [FunASR](https://github.com/modelscope/FunASR) - Speech recognition
- [pyannote](https://github.com/pyannote/pyannote-audio) - Speaker diarization
- [Transformers](https://github.com/huggingface/transformers) - Emotion recognition

