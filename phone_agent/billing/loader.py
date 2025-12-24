"""Pricing configuration loader."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import ModelPricing, PriceTier, ComplexPriceTier, PricingType
from .manager import BillingManager


def load_pricing_config(config_path: str | Path) -> BillingManager:
    """从 YAML 文件加载价格配置"""
    manager = BillingManager()

    config_path = Path(config_path)
    if not config_path.exists():
        print(f"⚠️ 价格配置文件不存在: {config_path}")
        return manager

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for model_config in config.get("models", []):
        # 处理简单阶梯定价
        if "tiers" in model_config:
            model_config["tiers"] = [
                PriceTier(**tier) for tier in model_config["tiers"]
            ]

        # 处理复杂阶梯定价
        if "complex_tiers" in model_config:
            model_config["complex_tiers"] = [
                ComplexPriceTier(**tier) for tier in model_config["complex_tiers"]
            ]

        # 处理 pricing_type
        if "pricing_type" in model_config:
            model_config["pricing_type"] = PricingType(model_config["pricing_type"])

        try:
            pricing = ModelPricing(**model_config)
            manager.register_pricing(pricing)
        except Exception as e:
            print(f"⚠️ 加载定价失败: {model_config.get('model', 'unknown')} - {e}")

    return manager


def create_default_billing_manager() -> BillingManager:
    """创建默认的计费管理器（使用内置价格）"""
    manager = BillingManager()

    default_pricing = [
        ModelPricing(
            vendor="OpenAI",
            model="gpt-4o",
            pricing_type=PricingType.FIXED,
            input_price_per_million=2.50,
            output_price_per_million=10.00,
        ),
        ModelPricing(
            vendor="OpenAI",
            model="gpt-4o-mini",
            pricing_type=PricingType.FIXED,
            input_price_per_million=0.15,
            output_price_per_million=0.60,
        ),
        ModelPricing(
            vendor="DeepSeek",
            model="deepseek-chat",
            pricing_type=PricingType.FIXED,
            input_price_per_million=0.14,
            output_price_per_million=0.28,
        ),
        ModelPricing(
            vendor="Google",
            model="gemini-2.0-flash",
            pricing_type=PricingType.FIXED,
            input_price_per_million=0.075,
            output_price_per_million=0.30,
        ),
        ModelPricing(
            vendor="Anthropic",
            model="claude-sonnet-4-20250514",
            pricing_type=PricingType.FIXED,
            input_price_per_million=3.00,
            output_price_per_million=15.00,
        ),
    ]

    for pricing in default_pricing:
        manager.register_pricing(pricing)

    return manager
