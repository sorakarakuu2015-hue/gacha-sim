from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    seed: int | None = None
    session_ttl: int = 3600
    session_max_size: int = 1000

    model_config = SettingsConfigDict(env_prefix="GACHA_", env_file=".env")


settings = Settings()
