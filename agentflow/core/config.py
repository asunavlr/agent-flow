from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./agentflow.db"
    max_workflow_nodes: int = Field(default=50, ge=1, le=500)
    max_execution_steps: int = Field(default=100, ge=1, le=1000)

@lru_cache
def get_settings() -> Settings:
    return Settings()
