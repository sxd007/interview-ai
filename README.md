# Interview AI - Interview Video Intelligence System

Multi-modal analysis system for psychological research and compliance investigation interviews.

## Features

- **Audio Processing**: STT, speaker diarization, denoising, prosody analysis
- **Video Analysis**: Face detection, action units (AU), emotion recognition
- **Psychological Analysis**: Stress signals, avoidance detection, confidence assessment
- **Multi-modal Fusion**: Combined audio + video emotion analysis
- **Timeline Visualization**: Synchronized playback with emotion curves

## Quick Start

### Prerequisites

- Python 3.10+
- CUDA 12.1+ (for GPU acceleration)
- FFmpeg

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd interview-ai

# Install dependencies
poetry install

# Download AI models
python scripts/download_models.py

# Start the application
docker-compose up -d
```

### Development

```bash
# Start API server
poetry run uvicorn src.api.main:app --reload

# Start frontend
cd frontend && npm install && npm run dev
```

## Project Structure

```
interview-ai/
├── src/
│   ├── api/           # FastAPI routes and schemas
│   ├── core/          # Configuration and utilities
│   ├── models/        # Database models
│   ├── services/      # Business logic
│   │   ├── audio/     # Audio processing
│   │   ├── video/     # Video analysis
│   │   └── emotion/   # Emotion analysis
│   ├── inference/     # Model inference
│   └── utils/         # Utilities
├── frontend/          # React frontend
├── models/            # Local model cache
├── tests/             # Test suite
├── docker/            # Docker configurations
└── docs/              # Documentation
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

MIT
