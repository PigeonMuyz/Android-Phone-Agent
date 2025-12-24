"""Billing data models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PricingType(str, Enum):
    """计费类型"""

    FIXED = "fixed"  # 固定价格
    TIERED = "tiered"  # 简单阶梯计费（按输入 token 数分档）
    TIERED_COMPLEX = "tiered_complex"  # 复杂阶梯计费（按输入+输出组合分档）
    FREE = "free"  # 完全免费


class PriceTier(BaseModel):
    """简单价格阶梯（按输入 token 数分档）"""

    min_tokens: int = Field(default=0, description="起始 token 数")
    max_tokens: int | None = Field(default=None, description="结束 token 数")
    input_price: float = Field(default=0.0, description="该区间输入价格 (/百万tokens)")
    output_price: float = Field(default=0.0, description="该区间输出价格 (/百万tokens)")


class ComplexPriceTier(BaseModel):
    """复杂价格阶梯（按输入+输出组合分档）
    
    适用于豆包等复杂定价模型：
    - 输入<=32k, 输出<=200: 特殊价格
    - 输入<=32k, 输出>200: 另一价格
    - 32k<输入<=128k: 另一档位
    - 输入>128k: 最高档位
    """

    # 输入条件
    input_min: int = Field(default=0, description="输入最小值")
    input_max: int | None = Field(default=None, description="输入最大值")
    
    # 输出条件（可选，不设置表示不限制）
    output_min: int | None = Field(default=None, description="输出最小值")
    output_max: int | None = Field(default=None, description="输出最大值")
    
    # 价格
    input_price: float = Field(default=0.0, description="该区间输入价格 (/百万tokens)")
    output_price: float = Field(default=0.0, description="该区间输出价格 (/百万tokens)")


class ModelPricing(BaseModel):
    """模型计费配置"""

    vendor: str = Field(description="供应商名称")
    model: str = Field(description="模型名称/ID")
    display_name: str | None = Field(default=None, description="显示名称")
    pricing_type: PricingType = Field(default=PricingType.FIXED)

    # 固定价格模式
    input_price_per_million: float = Field(default=0.0, description="输入价格 (/百万tokens)")
    output_price_per_million: float = Field(default=0.0, description="输出价格 (/百万tokens)")

    # 简单阶梯计费模式（按输入 token 分档）
    tiers: list[PriceTier] = Field(default_factory=list)
    
    # 复杂阶梯计费模式（按输入+输出组合分档）
    complex_tiers: list[ComplexPriceTier] = Field(default_factory=list)

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
    currency: str = "USD"


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
    currency: str = "USD"
    records: list[UsageRecord] = Field(default_factory=list)
