"""Abstract base class for VLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class VLMResponse(BaseModel):
    """统一响应格式"""

    thinking: str = Field(default="", description="模型思考过程")
    action: str = Field(default="", description="动作 JSON 字符串")
    raw_content: str = Field(default="", description="原始响应内容")
    
    # Token 统计 (用于计费)
    prompt_tokens: int = Field(default=0, description="输入 tokens")
    completion_tokens: int = Field(default=0, description="输出 tokens")
    total_tokens: int = Field(default=0, description="总 tokens")


class BaseVLMClient(ABC):
    """VLM 客户端抽象基类"""

    @abstractmethod
    def request(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """
        发送请求并获取响应
        
        Args:
            messages: 消息列表
            image: 可选的图像数据 (PNG)
            
        Returns:
            VLMResponse
        """
        pass

    @abstractmethod
    async def request_async(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """异步发送请求"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """模型名称 (用于计费查找)"""
        pass

    def parse_response(self, raw_content: str) -> tuple[str, str]:
        """
        解析响应为 (thinking, action)
        
        默认实现尝试从 JSON 中提取 thinking 和 action
        """
        import json
        import re

        thinking = ""
        action = ""

        # 尝试提取 JSON 块
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                thinking = data.get("thinking", "")
                action = json.dumps(
                    {k: v for k, v in data.items() if k != "thinking"},
                    ensure_ascii=False,
                )
                return thinking, action
            except json.JSONDecodeError:
                pass

        # 尝试直接解析整个内容为 JSON
        try:
            data = json.loads(raw_content)
            thinking = data.get("thinking", "")
            action = json.dumps(
                {k: v for k, v in data.items() if k != "thinking"},
                ensure_ascii=False,
            )
            return thinking, action
        except json.JSONDecodeError:
            pass

        # 无法解析，返回原始内容
        return "", raw_content
