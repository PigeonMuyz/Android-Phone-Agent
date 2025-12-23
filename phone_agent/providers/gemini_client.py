"""Google Gemini client."""

from __future__ import annotations

import asyncio
from typing import Any

import google.generativeai as genai
from PIL import Image
import io

from .base import BaseVLMClient, VLMResponse


class GeminiClient(BaseVLMClient):
    """Google Gemini 客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

        # 配置 API
        genai.configure(api_key=api_key)

        # 创建模型实例
        self._model = genai.GenerativeModel(
            model_name=model,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            },
        )

    @property
    def provider_name(self) -> str:
        return "Google"

    @property
    def model_name(self) -> str:
        return self.model

    def _extract_system_prompt(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """分离系统提示和对话消息"""
        system = ""
        conversation = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg.get("content", "")
            else:
                conversation.append(msg)

        return system, conversation

    def _convert_to_gemini_messages(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> list[dict[str, Any]]:
        """转换为 Gemini 消息格式"""
        gemini_messages = []

        for i, msg in enumerate(messages):
            role = "user" if msg["role"] == "user" else "model"
            content = msg.get("content", "")

            parts = []

            # 如果是最后一条用户消息且有图像
            if i == len(messages) - 1 and msg["role"] == "user" and image:
                img = Image.open(io.BytesIO(image))
                parts.append(img)

            parts.append(content)

            gemini_messages.append({
                "role": role,
                "parts": parts,
            })

        return gemini_messages

    def request(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """发送同步请求"""
        system, conversation = self._extract_system_prompt(messages)

        # 如果有系统提示，创建新的模型实例
        model = self._model
        if system:
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_output_tokens,
                },
                system_instruction=system,
            )

        gemini_messages = self._convert_to_gemini_messages(conversation, image)

        # 使用 chat 模式
        chat = model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])

        # 发送最后一条消息
        last_msg = gemini_messages[-1] if gemini_messages else {"parts": [""]}
        response = chat.send_message(last_msg["parts"])

        content = response.text

        thinking, action = self.parse_response(content)

        # Gemini 的 usage 统计
        usage_metadata = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0) if usage_metadata else 0
        completion_tokens = getattr(usage_metadata, "candidates_token_count", 0) if usage_metadata else 0

        return VLMResponse(
            thinking=thinking,
            action=action,
            raw_content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    async def request_async(
        self,
        messages: list[dict[str, Any]],
        image: bytes | None = None,
    ) -> VLMResponse:
        """发送异步请求 (使用线程池执行同步方法)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.request(messages, image)
        )
