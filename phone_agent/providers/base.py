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
        
        def extract_action_json(data: dict) -> str:
            """从数据中提取动作 JSON"""
            # 如果有 phase 字段，只提取 action 和 params
            if "phase" in data:
                if data.get("phase") == "plan":
                    return ""  # plan 阶段无需动作
                # execute/finish 阶段，只提取 action 和 params
                action_data = {}
                if "action" in data:
                    action_data["action"] = data["action"]
                if "params" in data:
                    action_data["params"] = data["params"]
                if action_data:
                    return json.dumps(action_data, ensure_ascii=False)
                return ""
            else:
                # 老格式：排除 thinking，保留其他
                return json.dumps(
                    {k: v for k, v in data.items() if k != "thinking"},
                    ensure_ascii=False,
                )

        def find_json_object(text: str) -> str | None:
            """找到完整的 JSON 对象（处理嵌套）"""
            start = text.find('{')
            if start == -1:
                return None
            
            depth = 0
            in_string = False
            escape = False
            
            for i, char in enumerate(text[start:], start):
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                    continue
                if char == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]
            return None

        # 尝试提取 JSON 块（代码块格式）
        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
        if code_block_match:
            json_str = find_json_object(code_block_match.group(1))
            if json_str:
                try:
                    data = json.loads(json_str)
                    thinking = data.get("thinking", "")
                    action = extract_action_json(data)
                    return thinking, action
                except json.JSONDecodeError:
                    pass

        # 尝试从原始内容找 JSON 对象
        json_str = find_json_object(raw_content)
        if json_str:
            try:
                data = json.loads(json_str)
                thinking = data.get("thinking", "")
                action = extract_action_json(data)
                return thinking, action
            except json.JSONDecodeError:
                pass

        # 无法解析，返回原始内容
        return "", raw_content
