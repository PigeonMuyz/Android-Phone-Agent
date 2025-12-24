"""Billing manager for cost tracking."""

from __future__ import annotations

from datetime import datetime

from .models import (
    ModelPricing,
    PricingType,
    UsageRecord,
    TaskBillingSummary,
)


class BillingManager:
    """计费管理器"""

    def __init__(self) -> None:
        self._pricing_registry: dict[str, ModelPricing] = {}
        self._usage_records: list[UsageRecord] = []
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_cost = 0.0

    def register_pricing(self, pricing: ModelPricing) -> None:
        """注册模型价格"""
        key = f"{pricing.vendor}:{pricing.model}"
        self._pricing_registry[key] = pricing

    def register_pricing_from_dict(self, config: dict) -> None:
        """从字典注册模型价格"""
        pricing = ModelPricing(**config)
        self.register_pricing(pricing)

    def get_pricing(self, vendor: str, model: str) -> ModelPricing | None:
        """获取模型价格配置"""
        key = f"{vendor}:{model}"
        return self._pricing_registry.get(key)

    def calculate_cost(
        self,
        vendor: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> tuple[float, float, float]:
        """
        计算调用成本

        Returns:
            (input_cost, output_cost, total_cost)
        """
        pricing = self.get_pricing(vendor, model)

        if pricing is None:
            # 未注册的模型，返回 0 成本
            return 0.0, 0.0, 0.0

        if pricing.pricing_type == PricingType.FREE:
            return 0.0, 0.0, 0.0

        if pricing.pricing_type == PricingType.FIXED:
            return self._calculate_fixed_cost(pricing, prompt_tokens, completion_tokens)

        if pricing.pricing_type == PricingType.TIERED:
            return self._calculate_tiered_cost(pricing, prompt_tokens, completion_tokens)

        if pricing.pricing_type == PricingType.TIERED_COMPLEX:
            return self._calculate_complex_tiered_cost(pricing, prompt_tokens, completion_tokens)

        return 0.0, 0.0, 0.0

    def _calculate_fixed_cost(
        self,
        pricing: ModelPricing,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> tuple[float, float, float]:
        """计算固定价格成本"""
        # 扣除免费额度
        billable_prompt = max(0, prompt_tokens - pricing.free_input_tokens)
        billable_completion = max(0, completion_tokens - pricing.free_output_tokens)

        input_cost = (billable_prompt / 1_000_000) * pricing.input_price_per_million
        output_cost = (billable_completion / 1_000_000) * pricing.output_price_per_million

        return input_cost, output_cost, input_cost + output_cost

    def _calculate_tiered_cost(
        self,
        pricing: ModelPricing,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> tuple[float, float, float]:
        """计算阶梯价格成本"""
        input_cost = 0.0
        output_cost = 0.0

        remaining_prompt = prompt_tokens
        remaining_completion = completion_tokens

        for tier in sorted(pricing.tiers, key=lambda t: t.min_tokens):
            if remaining_prompt <= 0 and remaining_completion <= 0:
                break

            tier_max = tier.max_tokens if tier.max_tokens else float("inf")
            tier_size = tier_max - tier.min_tokens

            # 计算该阶梯的输入 tokens
            prompt_in_tier = min(remaining_prompt, tier_size)
            if prompt_in_tier > 0:
                input_cost += (prompt_in_tier / 1_000_000) * tier.input_price
                remaining_prompt -= prompt_in_tier

            # 计算该阶梯的输出 tokens
            completion_in_tier = min(remaining_completion, tier_size)
            if completion_in_tier > 0:
                output_cost += (completion_in_tier / 1_000_000) * tier.output_price
                remaining_completion -= completion_in_tier

        return input_cost, output_cost, input_cost + output_cost

    def _calculate_complex_tiered_cost(
        self,
        pricing: ModelPricing,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> tuple[float, float, float]:
        """
        计算复杂阶梯价格成本（按输入+输出组合分档）
        
        适用于豆包等模型：
        - 输入<=32k, 输出<=200: 特殊价格
        - 输入<=32k, 输出>200: 另一价格
        - 32k<输入<=128k: 另一档位
        - 输入>128k: 最高档位
        """
        if not pricing.complex_tiers:
            # 没有复杂阶梯配置，回退到简单阶梯
            if pricing.tiers:
                return self._calculate_tiered_cost(pricing, prompt_tokens, completion_tokens)
            return 0.0, 0.0, 0.0

        # 找到匹配的档位
        matched_tier = None
        for tier in pricing.complex_tiers:
            # 检查输入条件
            input_match = tier.input_min <= prompt_tokens
            if tier.input_max is not None:
                input_match = input_match and prompt_tokens <= tier.input_max
            
            # 检查输出条件（如果有）
            output_match = True
            if tier.output_min is not None:
                output_match = completion_tokens >= tier.output_min
            if tier.output_max is not None:
                output_match = output_match and completion_tokens <= tier.output_max
            
            if input_match and output_match:
                matched_tier = tier
                break
        
        if matched_tier is None:
            # 没有匹配的档位，使用最后一个档位
            matched_tier = pricing.complex_tiers[-1]

        input_cost = (prompt_tokens / 1_000_000) * matched_tier.input_price
        output_cost = (completion_tokens / 1_000_000) * matched_tier.output_price

        return input_cost, output_cost, input_cost + output_cost

    def record_usage(
        self,
        vendor: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> UsageRecord:
        """记录一次调用并计算成本"""
        input_cost, output_cost, total_cost = self.calculate_cost(
            vendor, model, prompt_tokens, completion_tokens
        )

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            provider=vendor,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
        )

        self._usage_records.append(record)
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_cost += total_cost

        return record

    def get_task_summary(self) -> TaskBillingSummary:
        """获取当前任务的计费摘要"""
        if not self._usage_records:
            return TaskBillingSummary(
                provider="N/A",
                model="N/A",
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_input_cost=0.0,
                total_output_cost=0.0,
                total_cost=0.0,
                step_count=0,
            )

        last_record = self._usage_records[-1]
        total_input = sum(r.input_cost for r in self._usage_records)
        total_output = sum(r.output_cost for r in self._usage_records)

        return TaskBillingSummary(
            provider=last_record.provider,
            model=last_record.model,
            total_prompt_tokens=self._total_prompt_tokens,
            total_completion_tokens=self._total_completion_tokens,
            total_input_cost=total_input,
            total_output_cost=total_output,
            total_cost=self._total_cost,
            step_count=len(self._usage_records),
            records=self._usage_records,
        )

    def reset(self) -> None:
        """重置计费统计（新任务时调用）"""
        self._usage_records.clear()
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_cost = 0.0

    def export_report(self, format: str = "json") -> str:
        """导出计费报告"""
        summary = self.get_task_summary()
        if format == "json":
            return summary.model_dump_json(indent=2)
        return str(summary)
