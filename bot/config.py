from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: str = Field(alias="DISCORD_TOKEN")
    discord_guild_id: int = Field(alias="DISCORD_GUILD_ID")
    pubg_api_key: str = Field(alias="PUBG_API_KEY")
    db_path: str = Field(default="bot.db", alias="DB_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    admin_discord_id: int | None = Field(default=None, alias="ADMIN_DISCORD_ID")

    def validate_required_secrets(self) -> None:
        missing = [
            name
            for name, value in {
                "DISCORD_TOKEN": self.discord_token,
                "PUBG_API_KEY": self.pubg_api_key,
            }.items()
            if not value.strip()
        ]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
