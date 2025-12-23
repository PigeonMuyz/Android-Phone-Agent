"""Global settings for Phone Agent."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PHONE_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Profile 配置
    default_profile: str = Field(default="deepseek", description="默认使用的 Profile 名称")
    profiles_config_path: Path = Field(
        default=Path("config/profiles.yaml"),
        description="Profile 配置文件路径",
    )

    # 计费配置
    billing_enabled: bool = Field(default=True, description="是否启用计费追踪")
    billing_config_path: Path = Field(
        default=Path("config/pricing.yaml"),
        description="价格配置文件路径",
    )

    # App 缓存配置
    app_cache_dir: Path = Field(
        default=Path(".cache/apps"),
        description="App 列表缓存目录",
    )
    app_cache_ttl: int = Field(
        default=3600,
        description="App 缓存有效期（秒）",
    )

    # 日志配置
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="日志级别",
    )
    log_file: Path | None = Field(
        default=None,
        description="日志文件路径",
    )

    # Agent 配置
    max_steps: int = Field(default=50, description="单次任务最大步数")
    step_delay: float = Field(default=1.0, description="每步执行后的延迟（秒）")
    screenshot_scale: float = Field(default=0.5, description="截图缩放比例")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
