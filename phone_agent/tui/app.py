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

    TITLE = "Android Phone Agent"
    SUB_TITLE = "Multi-Provider VLM Automation"
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
        Binding("escape", "cancel_task", "取消任务"),
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
        self._current_agent = None  # 当前运行的 Agent
        self._task_running = False

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
            yield RichLog(id="log-panel", highlight=True, markup=True, wrap=True)
            
            with Horizontal(id="input-panel"):
                yield Input(
                    placeholder="输入任务描述，如：打开淘宝搜索蓝牙耳机",
                    id="task-input",
                )
                yield Button("执行", id="submit-btn", variant="primary")
                yield Button("暂停", id="pause-btn", variant="warning", disabled=True)
                yield Button("取消", id="cancel-btn", variant="error", disabled=True)

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
        elif event.button.id == "cancel-btn":
            await self.action_cancel_task()
        elif event.button.id == "pause-btn":
            await self.action_toggle_pause()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """输入提交事件"""
        if event.input.id == "task-input":
            await self._execute_task()

    async def _execute_task(self) -> None:
        """执行任务"""
        log = self.query_one("#log-panel", RichLog)
        task_input = self.query_one("#task-input", Input)
        select = self.query_one("#profile-select", Select)
        submit_btn = self.query_one("#submit-btn", Button)
        cancel_btn = self.query_one("#cancel-btn", Button)

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

        task_input.value = ""

        # 设置按钮状态
        submit_btn.disabled = True
        cancel_btn.disabled = False
        pause_btn = self.query_one("#pause-btn", Button)
        pause_btn.disabled = False
        self._task_running = True

        # 使用 Textual 的 worker 在后台执行
        self.run_worker(
            self._run_agent_worker(task, profile_name),
            exclusive=True,
            name="agent_task",
        )

    async def _run_agent_worker(self, task: str, profile_name: str) -> None:
        """在后台运行 Agent 任务（worker 版本）"""
        import queue

        log = self.query_one("#log-panel", RichLog)

        # 获取 Profile
        profile = self.profile_manager.get_profile(profile_name)
        if not profile:
            log.write(f"[red]Profile 不存在: {profile_name}[/red]")
            self._reset_buttons()
            return

        log.write(f"[blue]正在初始化...[/blue]")

        # 导入必要模块
        from phone_agent.adb import ADBDevice
        from phone_agent.agent import PhoneAgent, AgentConfig, StepResult
        from phone_agent.prompts import PromptManager
        from phone_agent.providers import create_vlm_client_from_profile
        from phone_agent.billing import load_pricing_config

        # 创建设备控制器
        device = ADBDevice(self._selected_device.device_id)
        log.write(f"[green]设备已连接[/green]")

        # 创建 VLM 客户端
        try:
            vlm_client = create_vlm_client_from_profile(profile)
            log.write(f"[green]VLM 客户端已创建: {profile.vendor}/{profile.model}[/green]")
        except Exception as e:
            log.write(f"[red]创建 VLM 客户端失败: {e}[/red]")
            self._reset_buttons()
            return

        # 加载 Prompt 管理器
        prompt_manager = PromptManager("prompts")
        prompt_manager.load()

        # 加载计费管理器
        billing_manager = None
        if self.settings.billing_enabled:
            billing_manager = load_pricing_config(self.settings.billing_config_path)

        # 用于线程间通信的队列
        step_queue = queue.Queue()

        def on_step(result: StepResult):
            """步骤完成回调"""
            step_queue.put(result)

        # 创建 Agent 配置
        config = AgentConfig(
            max_steps=self.settings.max_steps,
            action_delay=self.settings.action_delay,
            pause_on_action=False,
            verbose=False,
        )

        # 创建 Agent
        agent = PhoneAgent(
            config=config,
            vlm_client=vlm_client,
            device=device,
            prompt_manager=prompt_manager,
            billing_manager=billing_manager,
            profile=profile,
            on_step_callback=on_step,
        )
        self._current_agent = agent

        log.write(f"[blue]开始执行任务...[/blue]\n")

        # 在线程池中执行同步的 Agent
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        def run_sync():
            return agent.run(task)

        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(executor, run_sync)

            # 轮询队列更新日志
            while not future.done():
                await asyncio.sleep(0.1)
                
                # 处理队列中的步骤结果
                while not step_queue.empty():
                    try:
                        result: StepResult = step_queue.get_nowait()
                        self._display_step_result(log, result)
                    except queue.Empty:
                        break

            try:
                result = future.result()
                
                # 处理剩余的队列消息
                while not step_queue.empty():
                    try:
                        step_result = step_queue.get_nowait()
                        self._display_step_result(log, step_result)
                    except queue.Empty:
                        break
                
                log.write(f"\n[bold green]{'='*50}[/bold green]")
                log.write(f"[bold green]✅ 任务完成[/bold green]")
                log.write(f"[green]{result}[/green]")
                
                # 显示计费信息
                if billing_manager:
                    summary = billing_manager.get_task_summary()
                    if summary.step_count > 0:
                        log.write(f"\n[cyan]💰 成本统计:[/cyan]")
                        log.write(f"   输入: {summary.total_prompt_tokens:,} tokens")
                        log.write(f"   输出: {summary.total_completion_tokens:,} tokens")
                        log.write(f"   总成本: ¥{summary.total_cost:.4f}")
                        log.write(f"   步骤数: {summary.step_count}")
                
                log.write(f"[bold green]{'='*50}[/bold green]\n")
                
            except Exception as e:
                log.write(f"[red]执行错误: {e}[/red]")
                import traceback
                log.write(f"[dim]{traceback.format_exc()}[/dim]")

        self._reset_buttons()

    def _display_step_result(self, log: RichLog, result) -> None:
        """显示步骤结果"""
        status = "✅" if result.success else "❌"
        log.write(f"\n[bold cyan]━━━ 步骤 {self._current_agent._step_count if self._current_agent else '?'} {status}━━━[/bold cyan]")

        if result.thinking:
            # 显示思考过程（最多 200 字符）
            thinking_preview = result.thinking[:200]
            if len(result.thinking) > 200:
                thinking_preview += "..."
            log.write(f"[yellow]💭 思考:[/yellow] {thinking_preview}")

        if result.action:
            log.write(f"[blue]🎬 动作:[/blue] {result.action[:100]}...")

        if result.message:
            log.write(f"[green]📝 结果:[/green] {result.message}")

        if result.step_cost > 0:
            log.write(f"[dim]💰 成本: ¥{result.step_cost:.4f}[/dim]")

    def _reset_buttons(self) -> None:
        """重置按钮状态"""
        submit_btn = self.query_one("#submit-btn", Button)
        cancel_btn = self.query_one("#cancel-btn", Button)
        pause_btn = self.query_one("#pause-btn", Button)
        submit_btn.disabled = False
        cancel_btn.disabled = True
        pause_btn.disabled = True
        pause_btn.label = "暂停"
        self._task_running = False
        self._current_agent = None

    async def action_cancel_task(self) -> None:
        """取消当前任务"""
        if self._current_agent and self._task_running:
            log = self.query_one("#log-panel", RichLog)
            log.write("[yellow]⏹️ 正在取消任务...[/yellow]")
            self._current_agent.cancel()

    async def action_toggle_pause(self) -> None:
        """暂停/恢复任务"""
        if not self._current_agent or not self._task_running:
            return
        
        log = self.query_one("#log-panel", RichLog)
        pause_btn = self.query_one("#pause-btn", Button)
        
        if self._current_agent.is_paused():
            self._current_agent.resume()
            pause_btn.label = "暂停"
            log.write("[green]▶️ 任务已恢复[/green]")
        else:
            self._current_agent.pause()
            pause_btn.label = "继续"
            log.write("[yellow]⏸️ 任务已暂停 - 可手动操作手机，完成后点击「继续」[/yellow]")


def main() -> None:
    """TUI 入口点"""
    from dotenv import load_dotenv

    # 加载环境变量
    load_dotenv()

    app = PhoneAgentApp()
    app.run()


if __name__ == "__main__":
    main()
