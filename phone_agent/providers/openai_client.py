"""OpenAI-compatible client for OpenAI, DeepSeek, OpenRouter, etc."""

from __future__ import annotations

import base64
from typing import Any

from openai import OpenAI, AsyncOpenAI

from .base import BaseVLMClient, VLMResponse


class OpenAIClient(BaseVLMClient):
    """OpenAI 兼容客户端
    
    支持: OpenAI, DeepSeek, OpenRouter, 火山方舟, vLLM, SGLang 等
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        extra_headers: dict[str, str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.extra_headers = extra_headers
        self.temperature = temperature
        self.max_tokens = max_tokens

        self._client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=self.extra_headers,
            )
        return self._client

    @property
    def async_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=self.extra_headers,
            )
        return self._async_client

    @property
    def provider_name(self) -> str:
        if self.base_url:
            if "deepseek" in self.base_url.lower():
                return "DeepSeek"
            if "openrouter" in self.base_url.lower():
                return "OpenRouter"
            if "volces" in self.base_url.lower():
                return "火山方舟"
            if "localhost" in self.base_url.lower():
                return "Local"
        return "OpenAI"

    @property
    def model_name(self) -> str:
        return self.model

    def _build_messages(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> list[dict[str, Any]]:
        """构建消息列表，处理图像"""
        result = []

        for msg in messages:
            if msg["role"] == "user" and image is not None:
                # 添加图像到用户消息
                image_b64 = base64.b64encode(image).decode("utf-8")
                content = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": msg.get("content", "")},
                ]
                result.append({"role": "user", "content": content})
            else:
                result.append(msg)

        return result

    def request(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """发送同步请求"""
        built_messages = self._build_messages(messages, image)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=built_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        content = response.choices[0].message.content or ""
        usage = response.usage

        thinking, action = self.parse_response(content)

        return VLMResponse(
            thinking=thinking,
            action=action,
            raw_content=content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

    async def request_async(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """发送异步请求"""
        built_messages = self._build_messages(messages, image)

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=built_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        content = response.choices[0].message.content or ""
        usage = response.usage

        thinking, action = self.parse_response(content)

        return VLMResponse(
            thinking=thinking,
            action=action,
            raw_content=content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )
