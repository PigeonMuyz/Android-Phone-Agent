"""Action handler for executing device operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from phone_agent.adb import ADBDevice


class ActionType(str, Enum):
    """支持的动作类型"""

    TAP = "Tap"
    SWIPE = "Swipe"
    TYPE = "Type"
    LAUNCH = "Launch"
    BACK = "Back"
    HOME = "Home"
    WAIT = "Wait"
    LONG_PRESS = "Long Press"
    DOUBLE_TAP = "Double Tap"
    FINISH = "finish"
    PAUSE = "pause"


@dataclass
class ActionResult:
    """动作执行结果"""

    success: bool
    should_finish: bool
    message: str | None = None


class ActionHandler:
    """动作处理器"""

    def __init__(self, device: "ADBDevice") -> None:
        self.device = device
        self._handlers: dict[ActionType, Callable] = {
            ActionType.TAP: self._handle_tap,
            ActionType.SWIPE: self._handle_swipe,
            ActionType.TYPE: self._handle_type,
            ActionType.LAUNCH: self._handle_launch,
            ActionType.BACK: self._handle_back,
            ActionType.HOME: self._handle_home,
            ActionType.WAIT: self._handle_wait,
            ActionType.LONG_PRESS: self._handle_long_press,
            ActionType.DOUBLE_TAP: self._handle_double_tap,
            ActionType.FINISH: self._handle_finish,
            ActionType.PAUSE: self._handle_pause,
        }

    def execute(self, action_json: str) -> ActionResult:
        """
        执行动作

        Args:
            action_json: 动作 JSON 字符串

        Returns:
            ActionResult
        """
        try:
            action_data = json.loads(action_json)
        except json.JSONDecodeError:
            return ActionResult(False, False, f"无效的动作 JSON: {action_json[:100]}")

        action_type_str = action_data.get("action")
        if not action_type_str:
            return ActionResult(False, False, "缺少 action 字段")

        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            return ActionResult(False, False, f"未知动作类型: {action_type_str}")

        handler = self._handlers.get(action_type)
        if not handler:
            return ActionResult(False, False, f"未实现的动作: {action_type}")

        params = action_data.get("params", {})
        return handler(params)

    def _get_coords(self, element: list) -> tuple[int, int]:
        """
        将相对坐标 (0-1000) 转换为绝对像素

        Args:
            element: [x, y] 相对坐标

        Returns:
            (abs_x, abs_y) 绝对坐标
        """
        width, height = self.device.screen_size
        x = int(element[0] / 1000 * width)
        y = int(element[1] / 1000 * height)
        return x, y

    def _handle_tap(self, params: dict) -> ActionResult:
        """处理点击"""
        element = params.get("element", [500, 500])
        x, y = self._get_coords(element)

        if self.device.tap(x, y):
            return ActionResult(True, False, f"点击 ({x}, {y})")
        return ActionResult(False, False, "点击失败")

    def _handle_swipe(self, params: dict) -> ActionResult:
        """处理滑动"""
        element = params.get("element")
        direction = params.get("direction", "up")

        if element and len(element) >= 4:
            # 使用 [x1, y1, x2, y2] 坐标
            width, height = self.device.screen_size
            x1 = int(element[0] / 1000 * width)
            y1 = int(element[1] / 1000 * height)
            x2 = int(element[2] / 1000 * width)
            y2 = int(element[3] / 1000 * height)
            if self.device.swipe(x1, y1, x2, y2):
                return ActionResult(True, False, f"滑动 ({x1},{y1}) -> ({x2},{y2})")
        else:
            # 使用方向
            success = False
            if direction == "up":
                success = self.device.swipe_up()
            elif direction == "down":
                success = self.device.swipe_down()
            elif direction == "left":
                success = self.device.swipe_left()
            elif direction == "right":
                success = self.device.swipe_right()

            if success:
                return ActionResult(True, False, f"滑动 {direction}")

        return ActionResult(False, False, "滑动失败")

    def _handle_type(self, params: dict) -> ActionResult:
        """处理文本输入"""
        text = params.get("text", "")
        if not text:
            return ActionResult(False, False, "缺少输入文本")

        # 尝试使用 ADBKeyboard（支持中文）
        if self.device.input_text_adbime(text):
            return ActionResult(True, False, f"输入: {text[:20]}...")

        # 回退到普通输入
        if self.device.input_text(text):
            return ActionResult(True, False, f"输入: {text[:20]}...")

        return ActionResult(False, False, "输入失败")

    def _handle_launch(self, params: dict) -> ActionResult:
        """处理启动应用"""
        package = params.get("package", "")
        if not package:
            return ActionResult(False, False, "缺少 package 参数")

        if self.device.launch_app(package):
            return ActionResult(True, False, f"启动: {package}")
        return ActionResult(False, False, f"启动失败: {package}")

    def _handle_back(self, params: dict) -> ActionResult:
        """处理返回"""
        if self.device.press_back():
            return ActionResult(True, False, "返回")
        return ActionResult(False, False, "返回失败")

    def _handle_home(self, params: dict) -> ActionResult:
        """处理回到桌面"""
        if self.device.press_home():
            return ActionResult(True, False, "回到桌面")
        return ActionResult(False, False, "回到桌面失败")

    def _handle_wait(self, params: dict) -> ActionResult:
        """处理等待"""
        seconds = params.get("seconds", 1)
        import time
        time.sleep(seconds)
        return ActionResult(True, False, f"等待 {seconds} 秒")

    def _handle_long_press(self, params: dict) -> ActionResult:
        """处理长按"""
        element = params.get("element", [500, 500])
        duration = params.get("duration", 1000)
        x, y = self._get_coords(element)

        if self.device.long_press(x, y, duration):
            return ActionResult(True, False, f"长按 ({x}, {y})")
        return ActionResult(False, False, "长按失败")

    def _handle_double_tap(self, params: dict) -> ActionResult:
        """处理双击"""
        element = params.get("element", [500, 500])
        x, y = self._get_coords(element)

        if self.device.double_tap(x, y):
            return ActionResult(True, False, f"双击 ({x}, {y})")
        return ActionResult(False, False, "双击失败")

    def _handle_finish(self, params: dict) -> ActionResult:
        """处理任务完成"""
        message = params.get("message", "任务完成")
        return ActionResult(True, True, message)

    def _handle_pause(self, params: dict) -> ActionResult:
        """处理暂停等待用户"""
        message = params.get("message", "等待用户操作")
        return ActionResult(True, True, f"[暂停] {message}")
