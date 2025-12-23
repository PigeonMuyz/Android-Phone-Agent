"""Factory for creating VLM clients."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseVLMClient
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .gemini_client import GeminiClient

if TYPE_CHECKING:
    from phone_agent.config import ModelProfile


def create_vlm_client(
    protocol: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
    extra_headers: dict[str, str] | None = None,
    **kwargs,
) -> BaseVLMClient:
    """
    创建 VLM 客户端
    
    Args:
        protocol: 协议类型 (openai, anthropic, google)
        api_key: API Key
        model: 模型名称
        base_url: API Base URL
        extra_headers: 额外请求头
        **kwargs: 其他参数
        
    Returns:
        VLM 客户端实例
    """
    protocol = protocol.lower()

    if protocol == "openai":
        return OpenAIClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
            extra_headers=extra_headers,
            **kwargs,
        )
    elif protocol == "anthropic":
        return AnthropicClient(
            api_key=api_key,
            model=model,
            base_url=base_url,
            **kwargs,
        )
    elif protocol == "google":
        return GeminiClient(
            api_key=api_key,
            model=model,
            **kwargs,
        )
    else:
        raise ValueError(f"不支持的协议: {protocol}")


def create_vlm_client_from_profile(profile: "ModelProfile") -> BaseVLMClient:
    """
    根据 Profile 创建 VLM 客户端
    
    Args:
        profile: 模型配置档案
        
    Returns:
        VLM 客户端实例
    """
    return create_vlm_client(
        protocol=profile.protocol,
        api_key=profile.api_key,
        model=profile.model,
        base_url=profile.base_url,
        extra_headers=profile.extra_headers,
    )
