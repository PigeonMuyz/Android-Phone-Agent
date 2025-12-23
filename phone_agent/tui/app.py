"""Textual TUI application for Phone Agent."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    Static,
)

from phone_agent.adb import DeviceInfo, DeviceManager, DeviceState
from phone_agent.config import ProfileManager, get_settings


class DeviceListItem(ListItem):
    """设备列表项"""

    def __init__(self, device: DeviceInfo) -> None:
        super().__init__()
        self.device = device

    def compose(self) -> ComposeResult:
        status_icon = "🟢" if self.device.state == DeviceState.ONLINE else "🔴"
        if self.device.state == DeviceState.BUSY:
            status_icon = "🟡"

        label = f"{status_icon} {self.device.brand or ''} {self.device.model or self.device.device_id}"
        yield Label(label)


class PhoneAgentApp(App):
    """Phone Agent TUI 应用"""

    TITLE = "Phone Agent"
    SUB_TITLE = "Multi-Provider Android Automation"
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 2fr;
    }
    
    #sidebar {
        width: 100%;
        height: 100%;
        border: solid green;
    }
    
    #main-panel {
        width: 100%;
        height: 100%;
    }
    
    #device-list {
        height: auto;
        max-height: 50%;
        border: solid blue;
    }
    
    #profile-select {
        height: auto;
        margin: 1;
    }
    
    #log-panel {
        height: 1fr;
        border: solid cyan;
    }
    
    #input-panel {
        height: auto;
        dock: bottom;
        padding: 1;
    }
    
    #task-input {
        width: 1fr;
    }
    
    #submit-btn {
        width: auto;
        margin-left: 1;
    }
    
    .section-title {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("r", "refresh_devices", "刷新设备"),
        Binding("ctrl+c", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.device_manager = DeviceManager(
            cache_dir=self.settings.app_cache_dir,
            cache_ttl=self.settings.app_cache_ttl,
        )
        self.profile_manager = ProfileManager()
        self._selected_device: DeviceInfo | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="sidebar"):
            yield Static("📱 设备列表", classes="section-title")
            yield ListView(id="device-list")
            yield Static("🔧 模型配置", classes="section-title")
            yield Select(
                options=[],
                id="profile-select",
                prompt="选择 Profile",
            )

        with Container(id="main-panel"):
            yield Static("📋 任务日志", classes="section-title")
            yield RichLog(id="log-panel", highlight=True, markup=True)
            
            with Horizontal(id="input-panel"):
                yield Input(
                    placeholder="输入任务描述，如：打开淘宝搜索蓝牙耳机",
                    id="task-input",
                )
                yield Button("执行", id="submit-btn", variant="primary")

        yield Footer()

    async def on_mount(self) -> None:
        """应用启动时"""
        log = self.query_one("#log-panel", RichLog)
        log.write("[green]Phone Agent 启动成功![/green]")
        log.write("")

        # 加载 Profile
        await self._load_profiles()

        # 扫描设备
        await self._refresh_devices()

    async def _load_profiles(self) -> None:
        """加载 Profile 配置"""
        log = self.query_one("#log-panel", RichLog)
        select = self.query_one("#profile-select", Select)

        try:
            profiles_path = self.settings.profiles_config_path
            if profiles_path.exists():
                self.profile_manager.load_from_yaml(profiles_path)
                log.write(f"[blue]已加载 {len(self.profile_manager)} 个 Profile[/blue]")

                # 更新下拉选项
                options = [
                    (f"{p.vendor}/{p.model}", name)
                    for name, p in self.profile_manager.get_all_profiles().items()
                ]
                select.set_options(options)

                # 设置默认选项
                if self.profile_manager.default_profile_name:
                    select.value = self.profile_manager.default_profile_name
            else:
                log.write(f"[yellow]Profile 配置文件不存在: {profiles_path}[/yellow]")
        except Exception as e:
            log.write(f"[red]加载 Profile 失败: {e}[/red]")

    async def _refresh_devices(self) -> None:
        """刷新设备列表"""
        log = self.query_one("#log-panel", RichLog)
        device_list = self.query_one("#device-list", ListView)

        log.write("[blue]正在扫描设备...[/blue]")

        try:
            devices = self.device_manager.scan_devices()
            device_list.clear()

            if devices:
                for device in devices:
                    device_list.append(DeviceListItem(device))
                log.write(f"[green]发现 {len(devices)} 个设备[/green]")
            else:
                log.write("[yellow]未发现任何设备[/yellow]")
        except Exception as e:
            log.write(f"[red]设备扫描失败: {e}[/red]")
            log.write("[dim]请确保 ADB 服务已启动[/dim]")

    async def action_refresh_devices(self) -> None:
        """刷新设备动作"""
        await self._refresh_devices()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """设备选择事件"""
        log = self.query_one("#log-panel", RichLog)

        if isinstance(event.item, DeviceListItem):
            self._selected_device = event.item.device
            log.write(f"[green]已选择设备: {self._selected_device.model or self._selected_device.device_id}[/green]")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件"""
        if event.button.id == "submit-btn":
            await self._execute_task()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """输入提交事件"""
        if event.input.id == "task-input":
            await self._execute_task()

    async def _execute_task(self) -> None:
        """执行任务"""
        log = self.query_one("#log-panel", RichLog)
        task_input = self.query_one("#task-input", Input)
        select = self.query_one("#profile-select", Select)

        task = task_input.value.strip()
        if not task:
            log.write("[yellow]请输入任务描述[/yellow]")
            return

        if not self._selected_device:
            log.write("[yellow]请先选择一个设备[/yellow]")
            return

        profile_name = select.value
        if not profile_name or profile_name == Select.BLANK:
            log.write("[yellow]请先选择一个 Profile[/yellow]")
            return

        log.write(f"\n[bold cyan]{'='*50}[/bold cyan]")
        log.write(f"[bold]🎯 任务: {task}[/bold]")
        log.write(f"📱 设备: {self._selected_device.device_id}")
        log.write(f"🔧 Profile: {profile_name}")
        log.write(f"[bold cyan]{'='*50}[/bold cyan]\n")

        # 实际执行需要在后台线程运行，这里仅演示
        log.write("[blue]任务已提交...[/blue]")
        log.write("[dim]（完整执行功能待实现）[/dim]")

        task_input.value = ""


def main() -> None:
    """TUI 入口点"""
    from dotenv import load_dotenv

    # 加载环境变量
    load_dotenv()

    app = PhoneAgentApp()
    app.run()


if __name__ == "__main__":
    main()
