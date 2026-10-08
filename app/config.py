"""Server-only configuration. No key is exposed to templates or API responses."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_path: str = str(ROOT / "data" / "app.db")
    api_mode: str = "demo"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    timeout_seconds: float = 60
    upload_limit_bytes: int = 5 * 1024 * 1024
    max_pdf_pages: int = 40
    max_material_chars: int = 30_000

    @property
    def remote_ready(self) -> bool:
        return self.api_mode == "openai" and bool(self.api_key.strip())

    def validate(self) -> None:
        if self.api_mode not in {"demo", "openai"}:
            raise ValueError("API_MODE 必须为 demo 或 openai")
        parsed = urlparse(self.base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("LLM_BASE_URL 必须是没有凭据、查询参数及片段的 HTTPS 地址")
        if not self.model.strip() or len(self.model) > 100:
            raise ValueError("LLM_MODEL 不能为空或超过 100 字符")
        if not 1 <= self.timeout_seconds <= 180:
            raise ValueError("LLM_TIMEOUT_SECONDS 应为 1 到 180")


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    path = Path(os.getenv("DATABASE_PATH", "data/app.db"))
    if not path.is_absolute():
        path = ROOT / path
    settings = Settings(
        database_path=str(path),
        api_mode=os.getenv("API_MODE", "demo"),
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        model=os.getenv("LLM_MODEL", "deepseek-flash"),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
    )
    settings.validate()
    return settings
