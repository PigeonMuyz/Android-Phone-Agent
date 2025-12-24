"""Settings screen for TUI configuration management."""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
    TabbedContent,
    TabPane,
)


class SettingsScreen(Screen):
    """设置界面（全屏）"""

    BINDINGS = [
        Binding("escape", "go_back", "返回"),
        Binding("ctrl+s", "save_all", "保存"),
        Binding("q", "quit_app", "退出"),
    ]

    CSS = """
    SettingsScreen {
        layout: vertical;
    }
    
    #settings-main {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }
    
    TabbedContent {
        height: 100%;
    }
    
    TabPane {
        padding: 1;
    }
    
    .section-title {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
        margin-bottom: 1;
        width: 100%;
    }
    
    .form-row {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
        width: 100%;
    }
    
    .form-label {
        width: 20;
        height: 3;
        content-align: left middle;
    }
    
    .form-input {
        width: 1fr;
        height: auto;
    }
    
    #profile-list {
        height: 8;
        border: solid $primary;
        margin-bottom: 1;
        width: 100%;
    }
    
    #profile-buttons {
        height: 3;
        margin-bottom: 1;
        width: auto;
    }
    
    #profile-buttons Button {
        margin-right: 1;
    }
    
    #action-bar {
        height: 4;
        dock: bottom;
        background: $surface;
        border-top: solid $primary;
        padding: 1 2;
        width: 100%;
    }
    
    #action-bar Button {
        margin-right: 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._selected_profile: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="settings-main"):
            with TabbedContent():
                # API Keys Tab
                with TabPane("🔑 API Keys", id="tab-api-keys"):
                    yield Static("配置各厂商的 API Key：", classes="section-title")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("火山方舟:", classes="form-label")
                        yield Input(placeholder="VOLCANO_API_KEY", id="input-volcano-key", password=True, classes="form-input")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("OpenAI:", classes="form-label")
                        yield Input(placeholder="OPENAI_API_KEY", id="input-openai-key", password=True, classes="form-input")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("DeepSeek:", classes="form-label")
                        yield Input(placeholder="DEEPSEEK_API_KEY", id="input-deepseek-key", password=True, classes="form-input")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("Anthropic:", classes="form-label")
                        yield Input(placeholder="ANTHROPIC_API_KEY", id="input-anthropic-key", password=True, classes="form-input")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("Google:", classes="form-label")
                        yield Input(placeholder="GOOGLE_API_KEY", id="input-google-key", password=True, classes="form-input")

                # Profiles Tab
                with TabPane("📋 Profiles", id="tab-profiles"):
                    with VerticalScroll():
                        yield Static("模型配置列表：", classes="section-title")
                        yield ListView(id="profile-list")
                        
                        with Horizontal(id="profile-buttons"):
                            yield Button("新增", id="btn-add-profile", variant="success")
                            yield Button("编辑", id="btn-edit-profile", variant="primary")
                            yield Button("删除", id="btn-delete-profile", variant="error")
                        
                        yield Static("Profile 详情：", classes="section-title")
                        
                        with Horizontal(classes="form-row"):
                            yield Static("名称:", classes="form-label")
                            yield Input(id="profile-name", classes="form-input")
                        
                        with Horizontal(classes="form-row"):
                            yield Static("供应商:", classes="form-label")
                            yield Select(
                                options=[
                                    ("火山方舟", "火山方舟"),
                                    ("OpenAI", "OpenAI"),
                                    ("DeepSeek", "DeepSeek"),
                                    ("Anthropic", "Anthropic"),
                                    ("Google", "Google"),
                                ],
                                id="profile-vendor",
                                classes="form-input",
                            )
                        
                        with Horizontal(classes="form-row"):
                            yield Static("协议:", classes="form-label")
                            yield Select(
                                options=[
                                    ("openai", "openai"),
                                    ("anthropic", "anthropic"),
                                    ("gemini", "gemini"),
                                ],
                                id="profile-protocol",
                                classes="form-input",
                            )
                        
                        with Horizontal(classes="form-row"):
                            yield Static("模型:", classes="form-label")
                            yield Input(id="profile-model", classes="form-input")
                        
                        with Horizontal(classes="form-row"):
                            yield Static("Base URL:", classes="form-label")
                            yield Input(id="profile-base-url", classes="form-input")
                        
                        with Horizontal(classes="form-row"):
                            yield Static("API Key:", classes="form-label")
                            yield Input(id="profile-api-key", placeholder="留空使用环境变量", classes="form-input")

                # Basic Settings Tab
                with TabPane("⚙️ 基本设置", id="tab-settings"):
                    yield Static("运行参数配置：", classes="section-title")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("默认 Profile:", classes="form-label")
                        yield Select(options=[], id="setting-default-profile", classes="form-input")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("最大步数:", classes="form-label")
                        yield Input(id="setting-max-steps", classes="form-input", value="50")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("动作延迟(秒):", classes="form-label")
                        yield Input(id="setting-action-delay", classes="form-input", value="3.0")
                    
                    with Horizontal(classes="form-row"):
                        yield Static("摘要间隔:", classes="form-label")
                        yield Input(id="setting-summarize-interval", classes="form-input", value="5")

        with Horizontal(id="action-bar"):
            yield Button("↩️ 返回", id="btn-back", variant="default")
            yield Button("💾 保存", id="btn-save", variant="primary")
            yield Button("🚪 退出", id="btn-quit", variant="error")
        
        yield Footer()

    async def on_mount(self) -> None:
        """加载现有配置"""
        await self._load_api_keys()
        await self._load_profiles()
        await self._load_settings()

    async def _load_api_keys(self) -> None:
        """从环境变量加载 API Keys"""
        key_mapping = {
            "input-volcano-key": "VOLCANO_API_KEY",
            "input-openai-key": "OPENAI_API_KEY",
            "input-deepseek-key": "DEEPSEEK_API_KEY",
            "input-anthropic-key": "ANTHROPIC_API_KEY",
            "input-google-key": "GOOGLE_API_KEY",
        }
        
        for input_id, env_key in key_mapping.items():
            value = os.getenv(env_key, "")
            if value:
                try:
                    input_widget = self.query_one(f"#{input_id}", Input)
                    input_widget.value = value
                except Exception:
                    pass

    async def _load_profiles(self) -> None:
        """加载 Profile 列表"""
        try:
            from pathlib import Path
            from phone_agent.config import ProfileManager
            from phone_agent.config import get_settings
            
            settings = get_settings()
            manager = ProfileManager()
            
            # 需要先加载 YAML 文件
            profiles_path = Path(settings.profiles_config_path)
            if profiles_path.exists():
                manager.load_from_yaml(profiles_path)
            else:
                self.notify(f"配置文件不存在: {profiles_path}", severity="warning")
                return
            
            profile_list = self.query_one("#profile-list", ListView)
            profile_list.clear()
            
            profiles = manager.list_profiles()
            self.log(f"加载到 {len(profiles)} 个 profiles")
            
            for name in profiles:
                profile_list.append(ListItem(Static(name), id=f"profile-{name}"))
            
            # 更新默认 Profile 选择框
            default_select = self.query_one("#setting-default-profile", Select)
            options = [(name, name) for name in profiles]
            default_select.set_options(options)
            
        except Exception as e:
            self.log(f"加载 Profile 失败: {e}")
            self.notify(f"加载 Profile 失败: {e}", severity="error")

    async def _load_settings(self) -> None:
        """加载基本设置"""
        try:
            from phone_agent.config import get_settings
            settings = get_settings()
            
            self.query_one("#setting-max-steps", Input).value = str(settings.max_steps)
            self.query_one("#setting-action-delay", Input).value = str(settings.action_delay)
            self.query_one("#setting-summarize-interval", Input).value = str(settings.summarize_interval)
            
            default_select = self.query_one("#setting-default-profile", Select)
            if settings.default_profile:
                default_select.value = settings.default_profile
            
        except Exception as e:
            self.log(f"加载设置失败: {e}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件"""
        if event.button.id == "btn-save":
            await self._save_all()
        elif event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-quit":
            self.app.exit()
        elif event.button.id == "btn-add-profile":
            self._clear_profile_form()
            self._selected_profile = None
        elif event.button.id == "btn-edit-profile":
            await self._load_selected_profile()
        elif event.button.id == "btn-delete-profile":
            await self._delete_selected_profile()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Profile 列表选择事件"""
        if event.list_view.id == "profile-list":
            item_id = event.item.id or ""
            if item_id.startswith("profile-"):
                self._selected_profile = item_id.replace("profile-", "")
                self.notify(f"已选择: {self._selected_profile}")

    def _clear_profile_form(self) -> None:
        """清空 Profile 表单"""
        self.query_one("#profile-name", Input).value = ""
        self.query_one("#profile-model", Input).value = ""
        self.query_one("#profile-base-url", Input).value = ""
        self.query_one("#profile-api-key", Input).value = ""

    async def _load_selected_profile(self) -> None:
        """加载选中的 Profile 到表单"""
        if not self._selected_profile:
            self.notify("请先选择一个 Profile", severity="warning")
            return
        
        try:
            from pathlib import Path
            from phone_agent.config import ProfileManager, get_settings
            
            settings = get_settings()
            manager = ProfileManager()
            manager.load_from_yaml(Path(settings.profiles_config_path))
            
            profile = manager.get_profile(self._selected_profile)
            
            if profile:
                self.query_one("#profile-name", Input).value = self._selected_profile
                self.query_one("#profile-model", Input).value = profile.model
                self.query_one("#profile-base-url", Input).value = profile.base_url or ""
                self.query_one("#profile-api-key", Input).value = profile.api_key or ""
                
                vendor_select = self.query_one("#profile-vendor", Select)
                vendor_select.value = profile.vendor
                
                protocol_select = self.query_one("#profile-protocol", Select)
                protocol_select.value = profile.protocol
                
                self.notify(f"已加载: {self._selected_profile}")
                
        except Exception as e:
            self.notify(f"加载 Profile 失败: {e}", severity="error")

    async def _delete_selected_profile(self) -> None:
        """删除选中的 Profile"""
        if not self._selected_profile:
            self.notify("请先选择一个 Profile", severity="warning")
            return
        
        self.notify(f"删除功能待实现: {self._selected_profile}", severity="warning")

    async def _save_all(self) -> None:
        """保存所有配置"""
        try:
            await self._save_api_keys()
            await self._save_profile_form()
            await self._save_settings()
            self.notify("✅ 配置已保存", severity="information")
        except Exception as e:
            self.notify(f"保存失败: {e}", severity="error")

    async def _save_api_keys(self) -> None:
        """保存 API Keys 到 .env"""
        env_path = Path(".env")
        
        existing_lines = []
        if env_path.exists():
            existing_lines = env_path.read_text().splitlines()
        
        key_mapping = {
            "VOLCANO_API_KEY": self.query_one("#input-volcano-key", Input).value,
            "OPENAI_API_KEY": self.query_one("#input-openai-key", Input).value,
            "DEEPSEEK_API_KEY": self.query_one("#input-deepseek-key", Input).value,
            "ANTHROPIC_API_KEY": self.query_one("#input-anthropic-key", Input).value,
            "GOOGLE_API_KEY": self.query_one("#input-google-key", Input).value,
        }
        
        updated_keys = set()
        new_lines = []
        
        for line in existing_lines:
            updated = False
            for key, value in key_mapping.items():
                if line.startswith(f"{key}=") or line.startswith(f"# {key}="):
                    if value:
                        new_lines.append(f"{key}={value}")
                        updated_keys.add(key)
                    updated = True
                    break
            
            if not updated:
                new_lines.append(line)
        
        for key, value in key_mapping.items():
            if key not in updated_keys and value:
                new_lines.append(f"{key}={value}")
        
        env_path.write_text("\n".join(new_lines) + "\n")

    async def _save_profile_form(self) -> None:
        """保存 Profile 表单"""
        name = self.query_one("#profile-name", Input).value.strip()
        if not name:
            return
        
        try:
            import yaml
            
            profiles_path = Path("config/profiles.yaml")
            
            if profiles_path.exists():
                with open(profiles_path) as f:
                    data = yaml.safe_load(f) or {"profiles": {}}
            else:
                data = {"profiles": {}}
            
            vendor_select = self.query_one("#profile-vendor", Select)
            protocol_select = self.query_one("#profile-protocol", Select)
            
            profile_data = {
                "vendor": vendor_select.value if vendor_select.value != Select.BLANK else "OpenAI",
                "protocol": protocol_select.value if protocol_select.value != Select.BLANK else "openai",
                "model": self.query_one("#profile-model", Input).value,
                "base_url": self.query_one("#profile-base-url", Input).value or None,
                "api_key": self.query_one("#profile-api-key", Input).value or None,
            }
            
            data["profiles"][name] = profile_data
            
            with open(profiles_path, "w") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            
        except Exception as e:
            self.notify(f"保存 Profile 失败: {e}", severity="error")

    async def _save_settings(self) -> None:
        """保存基本设置到 .env"""
        env_path = Path(".env")
        
        existing_lines = []
        if env_path.exists():
            existing_lines = env_path.read_text().splitlines()
        
        default_profile_select = self.query_one("#setting-default-profile", Select)
        
        settings_mapping = {
            "PHONE_AGENT_DEFAULT_PROFILE": default_profile_select.value if default_profile_select.value != Select.BLANK else "",
            "PHONE_AGENT_MAX_STEPS": self.query_one("#setting-max-steps", Input).value,
            "PHONE_AGENT_ACTION_DELAY": self.query_one("#setting-action-delay", Input).value,
            "PHONE_AGENT_SUMMARIZE_INTERVAL": self.query_one("#setting-summarize-interval", Input).value,
        }
        
        updated_keys = set()
        new_lines = []
        
        for line in existing_lines:
            updated = False
            for key, value in settings_mapping.items():
                if line.startswith(f"{key}="):
                    if value:
                        new_lines.append(f"{key}={value}")
                        updated_keys.add(key)
                    updated = True
                    break
            
            if not updated:
                new_lines.append(line)
        
        for key, value in settings_mapping.items():
            if key not in updated_keys and value:
                new_lines.append(f"{key}={value}")
        
        env_path.write_text("\n".join(new_lines) + "\n")

    def action_go_back(self) -> None:
        """返回主界面"""
        self.app.pop_screen()

    async def action_save_all(self) -> None:
        """保存所有配置"""
        await self._save_all()

    def action_quit_app(self) -> None:
        """退出应用"""
        self.app.exit()
