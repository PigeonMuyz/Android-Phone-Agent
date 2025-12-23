"""Phone Agent core - the main agent loop."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from phone_agent.adb import ADBDevice
    from phone_agent.billing import BillingManager
    from phone_agent.config import ModelProfile
    from phone_agent.prompts import PromptManager, PromptContext
    from phone_agent.providers import BaseVLMClient

from .actions import ActionHandler


class AgentConfig(BaseModel):
    """Agent 配置"""

    max_steps: int = Field(default=50, description="最大步数")
    step_delay: float = Field(default=1.0, description="每步后延迟（秒）")
    screenshot_scale: float = Field(default=0.5, description="截图缩放比例")
    language: str = Field(default="zh", description="语言")
    verbose: bool = Field(default=True, description="详细输出")
    enable_billing: bool = Field(default=True, description="启用计费")


class StepResult(BaseModel):
    """单步执行结果"""

    success: bool
    finished: bool
    action: str | None = None
    thinking: str = ""
    message: str | None = None
    step_cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class PhoneAgent:
    """手机自动化智能体核心"""

    def __init__(
        self,
        config: AgentConfig,
        vlm_client: "BaseVLMClient",
        device: "ADBDevice",
        prompt_manager: "PromptManager",
        billing_manager: "BillingManager | None" = None,
        profile: "ModelProfile | None" = None,
    ) -> None:
        self.config = config
        self.vlm_client = vlm_client
        self.device = device
        self.prompt_manager = prompt_manager
        self.billing_manager = billing_manager
        self.profile = profile

        self.action_handler = ActionHandler(device)
        self._messages: list[dict] = []
        self._step_count = 0
        self._total_cost = 0.0

    def reset(self) -> None:
        """重置 Agent 状态"""
        self._messages.clear()
        self._step_count = 0
        self._total_cost = 0.0
        if self.billing_manager:
            self.billing_manager.reset()

    def run(self, task: str) -> str:
        """
        执行任务（同步）

        Args:
            task: 用户任务描述

        Returns:
            任务结果消息
        """
        self.reset()

        # 构建系统 Prompt
        from phone_agent.prompts import PromptContext

        context = PromptContext(
            task=task,
            current_app=self.device.get_current_app(),
            max_steps=self.config.max_steps,
        )
        system_prompt = self.prompt_manager.build_system_prompt(
            context, self.config.language
        )

        self._messages.append({"role": "system", "content": system_prompt})
        self._messages.append({"role": "user", "content": f"请完成以下任务：{task}"})

        if self.config.verbose:
            print(f"\n🎯 任务: {task}")
            print(f"📱 设备: {self.device.device_id}")
            print("-" * 50)

        while self._step_count < self.config.max_steps:
            result = self._execute_step()

            self._total_cost += result.step_cost

            if self.config.verbose:
                self._print_step_result(result)

            if result.finished:
                self._print_billing_summary()
                return result.message or "任务完成"

            time.sleep(self.config.step_delay)

        self._print_billing_summary()
        return "达到最大步数限制"

    def _execute_step(self) -> StepResult:
        """执行单步"""
        self._step_count += 1

        # 1. 截图
        screenshot = self.device.screenshot(scale=self.config.screenshot_scale)

        # 2. 调用 VLM
        response = self.vlm_client.request(self._messages, image=screenshot)

        # 3. 记录费用
        step_cost = 0.0
        if self.billing_manager and self.profile:
            record = self.billing_manager.record_usage(
                vendor=self.profile.vendor,
                model=self.profile.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )
            step_cost = record.total_cost

        # 4. 解析动作
        thinking = response.thinking
        action = response.action

        # 5. 执行动作
        action_result = self.action_handler.execute(action)

        # 6. 更新消息历史
        self._messages.append({
            "role": "assistant",
            "content": response.raw_content,
        })

        if not action_result.should_finish:
            # 添加执行结果作为用户反馈
            feedback = f"动作执行{'成功' if action_result.success else '失败'}"
            if action_result.message:
                feedback += f": {action_result.message}"
            self._messages.append({"role": "user", "content": feedback})

        return StepResult(
            success=action_result.success,
            finished=action_result.should_finish,
            action=action,
            thinking=thinking,
            message=action_result.message,
            step_cost=step_cost,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )

    def _print_step_result(self, result: StepResult) -> None:
        """打印步骤结果"""
        status = "✅" if result.success else "❌"
        print(f"\n[步骤 {self._step_count}] {status}")

        if result.thinking:
            # 只显示前 100 字符
            thinking_preview = result.thinking[:100]
            if len(result.thinking) > 100:
                thinking_preview += "..."
            print(f"💭 思考: {thinking_preview}")

        if result.action:
            print(f"🎬 动作: {result.action[:100]}...")

        if result.message:
            print(f"📝 结果: {result.message}")

        if result.step_cost > 0:
            print(f"💰 成本: ${result.step_cost:.6f}")

    def _print_billing_summary(self) -> None:
        """打印计费摘要"""
        if not self.billing_manager or not self.config.enable_billing:
            return

        summary = self.billing_manager.get_task_summary()
        if summary.step_count == 0:
            return

        print(f"\n{'=' * 50}")
        print("💰 任务成本统计:")
        print(f"   提供商: {summary.provider}")
        print(f"   模型: {summary.model}")
        print(f"   输入 Tokens: {summary.total_prompt_tokens:,}")
        print(f"   输出 Tokens: {summary.total_completion_tokens:,}")
        print(f"   总成本: ${summary.total_cost:.6f} (≈ ¥{summary.total_cost * 7.2:.4f})")
        print(f"   步骤数: {summary.step_count}")
        print(f"{'=' * 50}\n")
