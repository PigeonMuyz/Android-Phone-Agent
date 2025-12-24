"""Profile management for model configurations."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


ProtocolType = Literal["openai", "anthropic", "google"]


class ModelProfile(BaseModel):
    """模型配置档案"""

    name: str = Field(description="Profile 名称")
    vendor: str = Field(description="供应商显示名称")
    protocol: ProtocolType = Field(description="API 协议类型")
    base_url: str | None = Field(default=None, description="API Base URL")
    api_key: str = Field(description="API Key")
    model: str = Field(description="模型标识")
    description: str | None = Field(default=None, description="描述")
    is_free: bool = Field(default=False, description="是否为免费版本（不计费）")
    extra_headers: dict[str, str] | None = Field(
        default=None, description="额外请求头"
    )

    def __str__(self) -> str:
        free_tag = " (免费)" if self.is_free else ""
        return f"{self.vendor}/{self.model}{free_tag}"


class ProfileManager:
    """Profile 管理器"""

    def __init__(self) -> None:
        self._profiles: dict[str, ModelProfile] = {}
        self._default_profile_name: str | None = None

    def load_from_yaml(self, path: str | Path) -> None:
        """从 YAML 文件加载 Profiles"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Profile 配置文件不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self._default_profile_name = config.get("default_profile")

        profiles_config = config.get("profiles", {})
        for name, profile_data in profiles_config.items():
            # 处理环境变量引用 ${VAR_NAME}
            profile_data = self._expand_env_vars(profile_data)
            profile_data["name"] = name
            try:
                profile = ModelProfile(**profile_data)
                self._profiles[name] = profile
            except Exception as e:
                print(f"警告: 加载 Profile '{name}' 失败: {e}")

    def _expand_env_vars(self, data: dict) -> dict:
        """展开字典中的环境变量引用"""
        result = {}
        pattern = re.compile(r"\$\{([^}]+)\}")

        for key, value in data.items():
            if isinstance(value, str):
                # 替换 ${VAR_NAME} 为环境变量值
                def replacer(match: re.Match) -> str:
                    env_var = match.group(1)
                    return os.environ.get(env_var, f"${{{env_var}}}")

                result[key] = pattern.sub(replacer, value)
            elif isinstance(value, dict):
                result[key] = self._expand_env_vars(value)
            else:
                result[key] = value
        return result

    def get_profile(self, name: str) -> ModelProfile | None:
        """获取指定 Profile"""
        return self._profiles.get(name)

    def list_profiles(self) -> list[str]:
        """获取所有 Profile 名称"""
        return list(self._profiles.keys())

    def get_all_profiles(self) -> dict[str, ModelProfile]:
        """获取所有 Profiles"""
        return self._profiles.copy()

    @property
    def default_profile_name(self) -> str | None:
        """获取默认 Profile 名称"""
        return self._default_profile_name

    @property
    def default_profile(self) -> ModelProfile | None:
        """获取默认 Profile"""
        if self._default_profile_name:
            return self._profiles.get(self._default_profile_name)
        return None

    def __len__(self) -> int:
        return len(self._profiles)

    def __contains__(self, name: str) -> bool:
        return name in self._profiles
