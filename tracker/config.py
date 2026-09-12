"""Runtime configuration, loaded from environment variables.

All values have sane defaults for local/manual runs; docker-compose.yml sets
the ones that matter for a real deployment (token/data paths, interval, port).
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # no-op if there's no .env file; harmless in the container


@dataclass(frozen=True)
class Config:
    poll_interval_seconds: int
    web_port: int
    token_path: Path
    data_dir: Path

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "reading_log.jsonl"


def load_config() -> Config:
    return Config(
        poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "300")),
        web_port=int(os.environ.get("WEB_PORT", "8080")),
        token_path=Path(os.environ.get("TOKEN_PATH", "auth/token.json")),
        data_dir=Path(os.environ.get("DATA_DIR", "data")),
    )
