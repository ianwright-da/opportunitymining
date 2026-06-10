"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Runtime configuration for API clients."""

    apify_token: str
    google_creds_path: Path


def load_config() -> Config:
    """Load and validate configuration from .env and environment variables."""

    load_dotenv()

    apify_token = os.getenv("APIFY_TOKEN", "").strip()
    google_creds_path = os.getenv("GOOGLE_CREDS_PATH", "").strip()

    missing = []
    if not apify_token:
        missing.append("APIFY_TOKEN")
    if not google_creds_path:
        missing.append("GOOGLE_CREDS_PATH")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required environment variable(s): {joined}")

    creds_path = Path(google_creds_path).expanduser()
    if not creds_path.is_file():
        raise FileNotFoundError(
            f"GOOGLE_CREDS_PATH does not point to a readable file: {creds_path}"
        )

    return Config(apify_token=apify_token, google_creds_path=creds_path)
