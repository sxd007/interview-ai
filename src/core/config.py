from pathlib import Path
from typing import Literal, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "production", "testing"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Device configuration: auto, cpu, cuda, mps
    # auto: automatically detect (cuda > mps > cpu)
    device: str = "auto"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Interview AI API"
    api_version: str = "0.1.0"

    database_url: str = "sqlite:///./data/interview_ai.db"
    database_echo: bool = False

    upload_dir: Path = Path("./data/uploads")
    output_dir: Path = Path("./data/outputs")
    voice_print_dir: Path = Path("./data/voice_prints")
    max_upload_size: int = 2 * 1024 * 1024 * 1024  # 2GB

    model_cache_dir: Path = Path("./models")
    hf_token: str = ""

    stt_engine: str = "faster-whisper"
    stt_model: str = "large-v3-turbo"
    stt_language: str = "zh"
    diarization_model: str = "pyannote-3.1"

    max_concurrent_tasks: int = 2
    chunk_duration: int = 1800  # 30 minutes

    redis_url: str = "redis://localhost:6379/0"

    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def root_dir(self) -> Path:
        return Path(__file__).parent.parent.parent

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def ensure_directories(self) -> None:
        for directory in [self.upload_dir, self.output_dir, self.model_cache_dir, self.voice_print_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def get_device(self) -> str:
        """Get the actual device to use based on config and availability."""
        from src.utils.gpu import get_device as get_gpu_device
        return get_gpu_device(self.device)

    @property
    def is_gpu_available(self) -> bool:
        """Check if GPU is available."""
        import torch
        return torch.cuda.is_available() or torch.backends.mps.is_available()


settings = Settings()
