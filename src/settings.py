from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore",
                                      case_sensitive=False)

    github_token: str = ""
    github_repository: str = ""

    teams_channel_webhook: str = ""
    teams_dm_webhook: str = ""

    user_map_path: str = ""
