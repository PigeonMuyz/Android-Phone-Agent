"""Prompt manager for hierarchical prompt system.

三层 Prompt 体系:
1. 默认描述词 (Default) - 系统通用指令
2. App 专用描述词 (App-specific) - 针对特定应用的操作指南
3. 功能描述词 (Feature) - 针对特定任务的专业指令（如比价、搜索）
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from phone_agent.adb import DeviceInfo


class PromptContext(BaseModel):
    """Prompt 上下文"""

    task: str = Field(description="用户任务描述")
    current_app: str | None = Field(default=None, description="当前应用包名")
    device_info: dict | None = Field(default=None, description="设备信息")
    installed_apps: list[str] | None = Field(default=None, description="已安装应用列表")
    detected_feature: str | None = Field(default=None, description="检测到的功能类型")
    step_count: int = Field(default=0, description="当前步数")
    max_steps: int = Field(default=50, description="最大步数")
    history: list[dict] | None = Field(default=None, description="历史操作记录")


class AppPromptConfig(BaseModel):
    """App 专用 Prompt 配置"""

    name: str
    package: str
    aliases: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    scenarios: dict[str, dict] | None = None


class FeaturePromptConfig(BaseModel):
    """功能 Prompt 配置"""

    name: str
    trigger_keywords: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    examples: list[str] | None = None


class PromptManager:
    """三层 Prompt 管理器"""

    def __init__(self, prompts_dir: str | Path = "prompts") -> None:
        self.prompts_dir = Path(prompts_dir)
        self._system_prompts: dict[str, str] = {}
        self._app_prompts: dict[str, AppPromptConfig] = {}
        self._feature_prompts: dict[str, FeaturePromptConfig] = {}
        self._package_to_app: dict[str, str] = {}
        self._loaded = False

    def load(self) -> None:
        """加载所有 Prompt"""
        self._load_system_prompts()
        self._load_app_prompts()
        self._load_feature_prompts()
        self._loaded = True

    def _load_system_prompts(self) -> None:
        """加载系统默认 Prompt"""
        system_dir = self.prompts_dir / "system"
        if not system_dir.exists():
            return

        for prompt_file in system_dir.glob("*.md"):
            lang = prompt_file.stem.replace("default_", "")
            self._system_prompts[lang] = prompt_file.read_text(encoding="utf-8")

    def _load_app_prompts(self) -> None:
        """加载 App 专用 Prompt"""
        apps_dir = self.prompts_dir / "apps"
        if not apps_dir.exists():
            return

        for app_file in apps_dir.glob("*.yaml"):
            try:
                config = yaml.safe_load(app_file.read_text(encoding="utf-8"))
                app_config = AppPromptConfig(**config)
                
                # 存储多种索引方式
                self._app_prompts[app_config.name] = app_config
                self._package_to_app[app_config.package] = app_config.name
                
                for alias in app_config.aliases:
                    self._app_prompts[alias] = app_config
            except Exception as e:
                print(f"加载 App Prompt 失败 ({app_file}): {e}")

    def _load_feature_prompts(self) -> None:
        """加载功能描述词"""
        features_dir = self.prompts_dir / "features"
        if not features_dir.exists():
            return

        for feature_file in features_dir.glob("*.yaml"):
            try:
                config = yaml.safe_load(feature_file.read_text(encoding="utf-8"))
                feature_config = FeaturePromptConfig(**config)
                self._feature_prompts[feature_config.name] = feature_config
            except Exception as e:
                print(f"加载 Feature Prompt 失败 ({feature_file}): {e}")

    def detect_feature(self, task: str) -> str | None:
        """从任务描述中检测功能类型"""
        task_lower = task.lower()
        
        for feature_name, config in self._feature_prompts.items():
            for keyword in config.trigger_keywords:
                if keyword.lower() in task_lower:
                    return feature_name
        
        return None

    def get_app_config_by_package(self, package: str) -> AppPromptConfig | None:
        """通过包名获取 App 配置"""
        app_name = self._package_to_app.get(package)
        if app_name:
            return self._app_prompts.get(app_name)
        return None

    def build_system_prompt(
        self,
        context: PromptContext,
        lang: str = "zh",
    ) -> str:
        """
        构建完整的系统 Prompt
        
        组装顺序:
        1. 默认系统 Prompt
        2. App 专用 Prompt（如果有）
        3. 功能描述词（如果检测到）
        4. 设备/上下文信息
        """
        if not self._loaded:
            self.load()

        parts: list[str] = []

        # 1. 默认系统 Prompt
        default_prompt = self._system_prompts.get(lang) or self._system_prompts.get("zh", "")
        if default_prompt:
            parts.append(default_prompt)

        # 2. App 专用 Prompt
        if context.current_app:
            app_config = self.get_app_config_by_package(context.current_app)
            if app_config and app_config.system_prompt:
                parts.append(f"\n## {app_config.name} 操作指南\n\n{app_config.system_prompt}")

        # 3. 功能描述词
        feature = context.detected_feature or self.detect_feature(context.task)
        if feature and feature in self._feature_prompts:
            feature_config = self._feature_prompts[feature]
            parts.append(f"\n## {feature_config.name}功能提示\n\n{feature_config.system_prompt}")

        # 4. 设备和上下文信息
        context_info = self._build_context_info(context)
        if context_info:
            parts.append(f"\n## 当前状态\n\n{context_info}")

        return "\n".join(parts)

    def _build_context_info(self, context: PromptContext) -> str:
        """构建上下文信息部分"""
        lines: list[str] = []

        if context.device_info:
            device = context.device_info
            lines.append(f"- 设备: {device.get('brand', '')} {device.get('model', '')}")
            lines.append(f"- 屏幕: {device.get('screen_width', 1080)}x{device.get('screen_height', 1920)}")

        if context.current_app:
            lines.append(f"- 当前应用: {context.current_app}")

        if context.installed_apps:
            app_list = ", ".join(context.installed_apps[:20])  # 限制数量
            lines.append(f"- 已安装应用: {app_list}")
            if len(context.installed_apps) > 20:
                lines.append(f"  (共 {len(context.installed_apps)} 个)")

        lines.append(f"- 步骤: {context.step_count}/{context.max_steps}")

        return "\n".join(lines)

    def get_app_prompt(self, app_name: str) -> str:
        """获取 App 专用 Prompt"""
        if not self._loaded:
            self.load()
        
        config = self._app_prompts.get(app_name)
        return config.system_prompt if config else ""

    def get_feature_prompt(self, feature: str) -> str:
        """获取功能描述词"""
        if not self._loaded:
            self.load()
        
        config = self._feature_prompts.get(feature)
        return config.system_prompt if config else ""

    def list_apps(self) -> list[str]:
        """获取所有有专属 Prompt 的 App"""
        if not self._loaded:
            self.load()
        
        return [c.name for c in set(self._app_prompts.values())]

    def list_features(self) -> list[str]:
        """获取所有功能类型"""
        if not self._loaded:
            self.load()
        
        return list(self._feature_prompts.keys())
