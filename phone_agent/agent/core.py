"""Phone Agent core - the main agent loop."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from phone_agent.adb import ADBDevice
    from phone_agent.billing import BillingManager
    from phone_agent.config import ModelProfile
    from phone_agent.prompts import PromptManager, PromptContext
    from phone_agent.providers import BaseVLMClient

from .actions import ActionHandler

# 尝试导入 OCR（可选依赖）
try:
    from phone_agent.ocr import OCREngine
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    OCREngine = None


class AgentConfig(BaseModel):
    """Agent 配置"""

    max_steps: int = Field(default=50, description="最大步数")
    step_delay: float = Field(default=1.0, description="每步后延迟（秒）")
    action_delay: float = Field(default=3.0, description="动作执行后等待时间（秒）- 等待UI响应")
    screenshot_scale: float = Field(default=0.5, description="截图缩放比例")
    language: str = Field(default="zh", description="语言")
    verbose: bool = Field(default=True, description="详细输出")
    enable_billing: bool = Field(default=True, description="启用计费")
    pause_on_action: bool = Field(default=False, description="每步后暂停等待用户确认")
    enable_ocr: bool = Field(default=True, description="启用 OCR 辅助（检测键盘状态等）")
    
    # 成本优化：历史摘要
    summarize_interval: int = Field(default=5, description="每 N 步执行一次历史摘要（0=不摘要）")
    keep_system_prompt: bool = Field(default=True, description="始终保留系统 Prompt")


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
        on_step_callback: "Callable[[StepResult], None] | None" = None,
    ) -> None:
        self.config = config
        self.vlm_client = vlm_client
        self.device = device
        self.prompt_manager = prompt_manager
        self.billing_manager = billing_manager
        self.profile = profile
        self.on_step_callback = on_step_callback

        self.action_handler = ActionHandler(device)
        self._messages: list[dict] = []
        self._step_count = 0
        self._total_cost = 0.0
        self._cancelled = False
        
        # 初始化 OCR 引擎（可选）
        self._ocr_engine = None
        if config.enable_ocr and HAS_OCR:
            try:
                self._ocr_engine = OCREngine()
            except Exception:
                pass

    def reset(self) -> None:
        """重置 Agent 状态"""
        self._messages.clear()
        self._step_count = 0
        self._total_cost = 0.0
        self._cancelled = False
        self._paused = False
        if self.billing_manager:
            self.billing_manager.reset()

    def cancel(self) -> None:
        """取消任务"""
        self._cancelled = True
        self._paused = False

    def pause(self) -> None:
        """暂停任务"""
        self._paused = True

    def resume(self) -> None:
        """恢复任务"""
        self._paused = False

    def is_paused(self) -> bool:
        """检查是否暂停"""
        return self._paused

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
            # 检查是否被取消
            if self._cancelled:
                self._print_billing_summary()
                return "任务已取消"

            # 检查是否暂停（等待恢复）
            while self._paused and not self._cancelled:
                time.sleep(0.5)
            
            if self._cancelled:
                self._print_billing_summary()
                return "任务已取消"

            result = self._execute_step()

            self._total_cost += result.step_cost

            # 调用回调
            if self.on_step_callback:
                self.on_step_callback(result)

            if self.config.verbose:
                self._print_step_result(result)

            if result.finished:
                self._print_billing_summary()
                return result.message or "任务完成"

            # 历史摘要（每 N 步）
            if (self.config.summarize_interval > 0 and 
                self._step_count > 0 and 
                self._step_count % self.config.summarize_interval == 0):
                self._summarize_history()

            time.sleep(self.config.step_delay)

        self._print_billing_summary()
        return "达到最大步数限制"

    def _execute_step(self) -> StepResult:
        """执行单步"""
        self._step_count += 1

        # 1. 截图
        screenshot = self.device.screenshot(scale=self.config.screenshot_scale)
        
        # 1.5 OCR 分析（可选）
        ocr_context = ""
        if self._ocr_engine:
            try:
                ocr_context = self._ocr_engine.get_screen_context(screenshot)
            except Exception:
                pass

        # 2. 调用 VLM（如果有 OCR 上下文，添加到最后一条用户消息）
        messages_with_context = self._messages.copy()
        if ocr_context and messages_with_context:
            # 在请求前添加 OCR 上下文
            messages_with_context.append({
                "role": "user",
                "content": f"[屏幕分析]\n{ocr_context}"
            })
        
        response = self.vlm_client.request(messages_with_context, image=screenshot)

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

        # 6. 动作执行后等待 (等待 UI 响应)
        if action_result.success and not action_result.should_finish:
            if self.config.action_delay > 0:
                if self.config.verbose:
                    print(f"⏳ 等待 UI 响应 ({self.config.action_delay}s)...")
                time.sleep(self.config.action_delay)

        # 7. 用户介入暂停
        if self.config.pause_on_action and not action_result.should_finish:
            user_action = self._wait_for_user_input()
            if user_action == "stop":
                action_result.should_finish = True
                action_result.message = "用户手动停止任务"
            elif user_action == "skip":
                # 跳过本步反馈，直接继续
                pass

        # 8. 更新消息历史
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

    def _wait_for_user_input(self) -> str:
        """等待用户输入 (暂停模式)"""
        print("\n" + "=" * 50)
        print("⏸️  任务暂停 - 等待用户操作")
        print("=" * 50)
        print("  [Enter] 继续执行")
        print("  [s] 停止任务")
        print("  [m] 手动介入后继续 (不截图)")
        print("=" * 50)
        
        try:
            user_input = input("请选择: ").strip().lower()
            if user_input == "s":
                return "stop"
            elif user_input == "m":
                input("🔧 手动操作完成后按 Enter 继续...")
                return "skip"
            return "continue"
        except (EOFError, KeyboardInterrupt):
            return "stop"

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

    def _summarize_history(self) -> None:
        """将历史对话压缩为摘要以节省 token"""
        if len(self._messages) <= 3:  # 至少需要 system + user + 一些历史
            return

        if self.config.verbose:
            print("📝 正在压缩历史上下文...")

        # 保留系统 Prompt 和最后 4 条消息（保留更多上下文）
        system_msg = self._messages[0] if self._messages[0]["role"] == "system" else None
        recent_msgs = self._messages[-4:]  # 保留最近 4 条

        # 提取中间的历史消息
        if system_msg:
            history_msgs = self._messages[1:-4]
        else:
            history_msgs = self._messages[:-4]

        if not history_msgs:
            return

        # 改进的摘要：提取具体的动作、结果和关键信息
        import json
        import re
        
        completed_actions = []
        completed_tasks = []
        
        for i, msg in enumerate(history_msgs):
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "assistant":
                # 尝试提取 JSON 中的具体动作
                try:
                    # 尝试提取 JSON
                    json_match = re.search(r'\{[^{}]*"action"\s*:\s*"([^"]+)"[^{}]*\}', content, re.DOTALL)
                    if json_match:
                        action_type = json_match.group(1)
                        
                        # 提取 thinking
                        thinking_match = re.search(r'"thinking"\s*:\s*"([^"]{0,100})', content)
                        thinking = thinking_match.group(1) if thinking_match else ""
                        
                        if action_type.lower() == "finish":
                            # 记录任务完成
                            msg_match = re.search(r'"message"\s*:\s*"([^"]+)"', content)
                            if msg_match:
                                completed_tasks.append(msg_match.group(1)[:50])
                        else:
                            completed_actions.append(f"{action_type}: {thinking[:40]}...")
                except Exception:
                    pass
                    
            elif role == "user":
                # 检查是否包含成功/失败反馈
                if "动作执行成功" in content:
                    # 提取动作结果
                    if len(completed_actions) > 0:
                        completed_actions[-1] = completed_actions[-1].rstrip("...") + " ✓"
                elif "动作执行失败" in content:
                    if len(completed_actions) > 0:
                        completed_actions[-1] = completed_actions[-1].rstrip("...") + " ✗"

        # 构建更详细的摘要
        summary_parts = []
        
        if completed_tasks:
            summary_parts.append(f"【已完成的任务】\n" + "\n".join([f"✅ {t}" for t in completed_tasks]))
        
        if completed_actions:
            # 保留最多 15 个关键动作
            recent_actions = completed_actions[-15:]
            summary_parts.append(f"【执行的操作（第1-{self._step_count - 2}步）】\n" + "\n".join([f"• {a}" for a in recent_actions]))
        
        summary_content = f"""[历史摘要]
{chr(10).join(summary_parts)}

⚠️ 注意：以上任务已完成，不要重复执行！请根据当前屏幕状态继续下一步。
(已压缩 {len(history_msgs)} 条历史消息)"""

        # 重建消息列表
        self._messages = []
        if system_msg:
            self._messages.append(system_msg)
        self._messages.append({"role": "user", "content": summary_content})
        self._messages.extend(recent_msgs)

        if self.config.verbose:
            print(f"✅ 历史已压缩: {len(history_msgs)} 条 → 1 条摘要")
