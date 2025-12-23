"""Billing data models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PricingType(str, Enum):
    """计费类型"""

    FIXED = "fixed"  # 固定价格
    TIERED = "tiered"  # 阶梯计费
    FREE = "free"  # 完全免费


class PriceTier(BaseModel):
    """价格阶梯（用于区间计费）"""

    min_tokens: int = Field(default=0, description="起始 token 数")
    max_tokens: int | None = Field(default=None, description="结束 token 数")
    input_price: float = Field(description="该区间输入价格 ($/百万tokens)")
    output_price: float = Field(description="该区间输出价格 ($/百万tokens)")


class ModelPricing(BaseModel):
    """模型计费配置"""

    vendor: str = Field(description="供应商名称")
    model: str = Field(description="模型名称/ID")
    display_name: str | None = Field(default=None, description="显示名称")
    pricing_type: PricingType = Field(default=PricingType.FIXED)

    # 固定价格模式
    input_price_per_million: float = Field(default=0.0, description="输入价格 ($/百万tokens)")
    output_price_per_million: float = Field(default=0.0, description="输出价格 ($/百万tokens)")

    # 阶梯计费模式
    tiers: list[PriceTier] = Field(default_factory=list)

    # 免费额度
    free_input_tokens: int = Field(default=0, description="每月免费输入 tokens")
    free_output_tokens: int = Field(default=0, description="每月免费输出 tokens")

    # 元数据
    currency: str = Field(default="USD", description="货币单位")
    last_updated: str | None = Field(default=None, description="价格更新日期")
    notes: str | None = Field(default=None, description="备注")


class UsageRecord(BaseModel):
    """单次调用记录"""

    timestamp: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float


class TaskBillingSummary(BaseModel):
    """任务计费摘要"""

    provider: str
    model: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_input_cost: float
    total_output_cost: float
    total_cost: float
    step_count: int
    records: list[UsageRecord] = Field(default_factory=list)
