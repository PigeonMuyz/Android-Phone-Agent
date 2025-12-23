"""Anthropic Claude client."""

from __future__ import annotations

import base64
from typing import Any

import anthropic

from .base import BaseVLMClient, VLMResponse


class AnthropicClient(BaseVLMClient):
    """Anthropic Claude 客户端"""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens

        self._client: anthropic.Anthropic | None = None
        self._async_client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    @property
    def async_client(self) -> anthropic.AsyncAnthropic:
        if self._async_client is None:
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._async_client = anthropic.AsyncAnthropic(**kwargs)
        return self._async_client

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    @property
    def model_name(self) -> str:
        return self.model

    def _extract_system_and_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """分离 system 消息和对话消息（Anthropic API 要求）"""
        system = ""
        conversation = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg.get("content", "")
            else:
                conversation.append(msg)

        return system, conversation

    def _build_content(
        self,
        text: str,
        image: bytes | None = None,
    ) -> list[dict[str, Any]]:
        """构建 Anthropic 格式的 content"""
        content = []

        if image is not None:
            image_b64 = base64.b64encode(image).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_b64,
                },
            })

        content.append({"type": "text", "text": text})
        return content

    def request(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """发送同步请求"""
        system, conversation = self._extract_system_and_messages(messages)

        # 处理最后一条用户消息添加图像
        if conversation and conversation[-1]["role"] == "user":
            text = conversation[-1].get("content", "")
            conversation[-1]["content"] = self._build_content(text, image)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system if system else anthropic.NOT_GIVEN,
            messages=conversation,
        )

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        thinking, action = self.parse_response(content)

        return VLMResponse(
            thinking=thinking,
            action=action,
            raw_content=content,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

    async def request_async(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """发送异步请求"""
        system, conversation = self._extract_system_and_messages(messages)

        if conversation and conversation[-1]["role"] == "user":
            text = conversation[-1].get("content", "")
            conversation[-1]["content"] = self._build_content(text, image)

        response = await self.async_client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system if system else anthropic.NOT_GIVEN,
            messages=conversation,
        )

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        thinking, action = self.parse_response(content)

        return VLMResponse(
            thinking=thinking,
            action=action,
            raw_content=content,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )
