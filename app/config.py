from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    github_token: str = ""
    cache_enabled: bool = True
    cache_ttl: int = 604800  # 1 week in seconds
    cache_dir: str = ".cache"

    model_config = {"env_file": ".env"}


settings = Settings()
