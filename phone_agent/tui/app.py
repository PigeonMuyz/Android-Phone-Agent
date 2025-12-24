"""Textual TUI application for Phone Agent."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from textual.app import App, ComposeResult, on
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
        Binding("s", "open_settings", "设置"),
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
        self._user_prefs_path = Path(".cache/user_prefs.json")  # 用户偏好文件
        
        # 任务面板
        self._show_current_task = True  # True=当前任务, False=历史
        self._current_task_info = {"name": "", "cost": 0.0, "time": 0}
        self._task_history: list[dict] = []
        self._task_start_time: float = 0

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
            
            # 任务状态面板
            with Vertical(id="task-panel"):
                with Horizontal(id="task-panel-header"):
                    yield Static("📊 ", id="task-panel-icon")
                    yield Button("当前任务", id="show-current-btn", variant="primary")
                    yield Button("历史", id="show-history-btn", variant="default")
                yield Static("", id="task-status-content", classes="task-content")
            
            # 设置按钮
            yield Button("⚙️ 设置", id="settings-btn", variant="default")

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

                # 按 vendor 分组显示
                all_profiles = self.profile_manager.get_all_profiles()
                
                # 按 vendor 分组
                grouped: dict[str, list[tuple[str, str, str]]] = {}
                for name, p in all_profiles.items():
                    vendor = p.vendor
                    if vendor not in grouped:
                        grouped[vendor] = []
                    # 显示名称：description 或 model 名
                    display = p.description or p.model
                    if p.is_free:
                        display += " 🆓"
                    grouped[vendor].append((name, display, vendor))
                
                # 构建选项列表（带 vendor 分隔标题）
                options = []
                for vendor in sorted(grouped.keys()):
                    # 添加 vendor 作为分隔标题（使用特殊前缀标记）
                    options.append((f"━━ {vendor} ━━", f"__vendor__{vendor}"))
                    for name, display, _ in grouped[vendor]:
                        options.append((f"    {display}", name))
                
                select.set_options(options)

                # 设置默认选项：优先使用用户上次选择，其次使用配置中的默认值
                saved_profile = self._load_user_pref("last_profile")
                valid_profile_names = [val for _, val in options if not str(val).startswith("__vendor__")]
                if saved_profile and saved_profile in valid_profile_names:
                    select.value = saved_profile
                elif self.profile_manager.default_profile_name:
                    select.value = self.profile_manager.default_profile_name
            else:
                log.write(f"[yellow]Profile 配置文件不存在: {profiles_path}[/yellow]")
        except Exception as e:
            log.write(f"[red]加载 Profile 失败: {e}[/red]")

    def _load_user_pref(self, key: str) -> str | None:
        """加载用户偏好"""
        try:
            if self._user_prefs_path.exists():
                import json
                prefs = json.loads(self._user_prefs_path.read_text())
                return prefs.get(key)
        except Exception:
            pass
        return None

    def _save_user_pref(self, key: str, value: str) -> None:
        """保存用户偏好"""
        try:
            import json
            self._user_prefs_path.parent.mkdir(parents=True, exist_ok=True)
            prefs = {}
            if self._user_prefs_path.exists():
                prefs = json.loads(self._user_prefs_path.read_text())
            prefs[key] = value
            self._user_prefs_path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2))
        except Exception:
            pass

    @on(Select.Changed, "#profile-select")
    def on_profile_select_changed(self, event: Select.Changed) -> None:
        """当用户选择模型时保存（忽略 vendor 分隔符）"""
        if event.value and event.value != Select.BLANK:
            # 忽略 vendor 分隔符
            if str(event.value).startswith("__vendor__"):
                return
            self._save_user_pref("last_profile", str(event.value))

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
        elif event.button.id == "show-current-btn":
            self._show_current_task = True
            self._update_task_panel_buttons()
            self._update_task_panel()
        elif event.button.id == "show-history-btn":
            self._show_current_task = False
            self._update_task_panel_buttons()
            self._update_task_panel()
        elif event.button.id == "settings-btn":
            await self.action_open_settings()

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
        
        # 任务进行时添加取消任务绑定
        self.bind("escape", "cancel_task", description="取消任务")
        self.refresh_bindings()

        # 记录任务信息
        import time as time_module
        self._task_start_time = time_module.time()
        self._current_task_info = {"name": task, "cost": 0.0, "time": 0}
        self._update_task_panel()

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
        from phone_agent.agent import PhoneAgent, AgentConfig, StepResult, ProgressUpdate
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
        progress_queue = queue.Queue()

        def on_step(result: StepResult):
            """步骤完成回调"""
            step_queue.put(result)

        def on_progress(update: ProgressUpdate):
            """实时进度回调"""
            progress_queue.put(update)

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
            on_progress_callback=on_progress,
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
                
                # 先处理进度更新（实时显示思考/动作）
                while not progress_queue.empty():
                    try:
                        progress: ProgressUpdate = progress_queue.get_nowait()
                        self._display_progress(log, progress)
                    except queue.Empty:
                        break
                
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
                error_msg = self._simplify_error(str(e))
                log.write(f"[red]❌ {error_msg}[/red]")

        self._reset_buttons()

    def _simplify_error(self, error: str) -> str:
        """将错误信息简化为友好提示"""
        error_lower = error.lower()
        
        # 常见错误映射
        if "model do not support image input" in error_lower or "image input" in error_lower:
            return "错误：当前模型不支持图片输入，请切换到视觉模型（如 doubao-vision）"
        elif "api key" in error_lower or "authentication" in error_lower or "unauthorized" in error_lower:
            return "错误：API Key 无效或未配置，请在设置中检查 API Key"
        elif "rate limit" in error_lower:
            return "错误：请求过于频繁，已触发限流，请稍后再试"
        elif "timeout" in error_lower:
            return "错误：请求超时，请检查网络连接"
        elif "connection" in error_lower:
            return "错误：网络连接失败，请检查网络"
        elif "quota" in error_lower or "insufficient" in error_lower:
            return "错误：账户余额不足或配额已用完"
        elif "invalid" in error_lower and "model" in error_lower:
            return "错误：模型名称无效，请检查 Profile 配置"
        elif "base_url" in error_lower or "endpoint" in error_lower:
            return "错误：API 地址无效，请检查 Profile 中的 Base URL 配置"
        else:
            # 截取错误消息的关键部分
            if len(error) > 100:
                return f"错误：{error[:100]}..."
            return f"错误：{error}"

    def _display_step_result(self, log: RichLog, result) -> None:
        """显示步骤结果（成本和完成标记）"""
        # 进度已通过 on_progress_callback 实时显示，这里只显示完成状态和成本
        status = "✅" if result.success else "❌"
        log.write(f"[dim]━━━ 步骤完成 {status} ━━━[/dim]")

        if result.step_cost > 0:
            log.write(f"[dim]💰 成本: ¥{result.step_cost:.4f}[/dim]")
            # 更新任务面板成本
            self._current_task_info["cost"] += result.step_cost
            self._update_task_panel()

    def _display_progress(self, log: RichLog, progress) -> None:
        """显示实时进度（思考/动作/等待）"""
        if progress.phase == "thinking":
            # 显示步骤头和思考
            log.write(f"\n[bold cyan]━━━ 步骤 {progress.step} ━━━[/bold cyan]")
            if progress.thinking:
                thinking_preview = progress.thinking[:200]
                if len(progress.thinking) > 200:
                    thinking_preview += "..."
                log.write(f"[yellow]💭 思考:[/yellow] {thinking_preview}")
            if progress.action:
                log.write(f"[blue]🎬 动作:[/blue] {progress.action[:100]}...")
        elif progress.phase == "action":
            if progress.message:
                log.write(f"[green]📝 结果:[/green] {progress.message}")
        elif progress.phase == "waiting":
            log.write(f"[dim]⏳ {progress.message}[/dim]")

    def _reset_buttons(self) -> None:
        """重置按钮状态"""
        submit_btn = self.query_one("#submit-btn", Button)
        cancel_btn = self.query_one("#cancel-btn", Button)
        pause_btn = self.query_one("#pause-btn", Button)
        submit_btn.disabled = False
        cancel_btn.disabled = True
        pause_btn.disabled = True
        pause_btn.label = "暂停"
        
        # 保存任务到历史
        if self._current_task_info.get("name"):
            self._task_history.append({
                "name": self._current_task_info["name"],
                "cost": self._current_task_info["cost"],
            })
        
        self._task_running = False
        self._current_agent = None
        self._current_task_info = {"name": "", "cost": 0.0, "time": 0}
        self._update_task_panel()
        
        # 移除取消任务绑定
        try:
            # 移除动态绑定的 escape
            self._bindings.key_to_bindings.pop("escape", None)
            self.refresh_bindings()
        except Exception:
            pass

    async def action_cancel_task(self) -> None:
        """取消当前任务"""
        if self._current_agent and self._task_running:
            log = self.query_one("#log-panel", RichLog)
            log.write("[yellow]⏹️ 正在取消任务...[/yellow]")
            self._current_agent.cancel()
            
            # 立即重置 UI 状态，不等待后台任务完成
            self._reset_buttons()
            log.write("[yellow]任务已取消（后台请求可能仍在完成中）[/yellow]")

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

    async def action_open_settings(self) -> None:
        """打开设置界面"""
        from phone_agent.tui.screens.settings import SettingsScreen
        self.push_screen(SettingsScreen())

    def _update_task_panel_buttons(self) -> None:
        """更新任务面板按钮样式"""
        current_btn = self.query_one("#show-current-btn", Button)
        history_btn = self.query_one("#show-history-btn", Button)
        
        if self._show_current_task:
            current_btn.variant = "primary"
            history_btn.variant = "default"
        else:
            current_btn.variant = "default"
            history_btn.variant = "primary"

    def _update_task_panel(self) -> None:
        """更新任务面板内容"""
        content = self.query_one("#task-status-content", Static)
        
        if self._show_current_task:
            # 显示当前任务
            if self._task_running and self._current_task_info["name"]:
                import time as time_module
                elapsed = int(time_module.time() - self._task_start_time)
                mins, secs = divmod(elapsed, 60)
                
                status = "⏸️ 暂停" if (self._current_agent and self._current_agent.is_paused()) else "▶️ 执行中"
                
                text = f"""🎯 {self._current_task_info['name'][:20]}...
{status}
⏱️ {mins}m {secs}s
💰 ¥{self._current_task_info['cost']:.4f}"""
            else:
                text = "[dim]无正在执行的任务[/dim]"
        else:
            # 显示历史任务
            if self._task_history:
                lines = []
                for i, task in enumerate(self._task_history[-5:]):  # 最近5个
                    lines.append(f"{i+1}. {task['name'][:15]}.. ¥{task['cost']:.4f}")
                text = "\n".join(lines)
            else:
                text = "[dim]暂无历史记录[/dim]"
        
        content.update(text)


def main() -> None:
    """TUI 入口点"""
    from dotenv import load_dotenv

    # 加载环境变量
    load_dotenv()

    app = PhoneAgentApp()
    app.run()


if __name__ == "__main__":
    main()
