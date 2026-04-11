import json
import os
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    DATABASE_NAME: str = "bedrock"
    MODE: str = "development"
    GEMINI_API_KEYS: list[str] = Field(default_factory=list)
    OPENAI_API_KEY: str
    USE_VISION_MODEL: bool = (
        True  # VLM support for vision parsing; set False in .env to disable.
    )
    LOCAL_BASE_URL: str = "http://localhost"

    @field_validator("GEMINI_API_KEYS", mode="before")
    @classmethod
    def parse_api_keys(cls, value: Any) -> list[str]:
        """Accept JSON array/comma-separated GEMINI_API_KEYS with legacy API_KEY_N fallback."""
        api_keys_explicitly_set = "GEMINI_API_KEYS" in os.environ
        legacy_key_names = sorted(
            [
                env_name
                for env_name in os.environ
                if env_name.startswith("API_KEY_")
                and env_name[len("API_KEY_") :].isdigit()
            ],
            key=lambda name: int(name[len("API_KEY_") :]),
        )
        legacy_keys = [
            os.environ[name].strip()
            for name in legacy_key_names
            if os.environ.get(name, "").strip()
        ]

        if value is None:
            return legacy_keys

        if isinstance(value, list):
            parsed = [str(item).strip() for item in value if str(item).strip()]
            if parsed or api_keys_explicitly_set:
                return parsed
            return legacy_keys

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return [] if api_keys_explicitly_set else legacy_keys

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, list):
                parsed_list = [
                    str(item).strip() for item in parsed if str(item).strip()
                ]
                if parsed_list or api_keys_explicitly_set:
                    return parsed_list
                return legacy_keys

            parsed_list = [item.strip() for item in raw.split(",") if item.strip()]
            if parsed_list or api_keys_explicitly_set:
                return parsed_list
            return legacy_keys

        raise ValueError(
            "GEMINI_API_KEYS must be a JSON array or a comma-separated string"
        )

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
