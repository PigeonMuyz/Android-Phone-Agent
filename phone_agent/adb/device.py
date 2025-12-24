"""Single device controller using adbutils."""

from __future__ import annotations

import io
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from adbutils import AdbClient, AdbDevice
from PIL import Image

if TYPE_CHECKING:
    from .device_manager import DeviceManager


class ADBDevice:
    """单个设备控制器"""

    def __init__(
        self,
        device_id: str,
        host: str = "127.0.0.1",
        port: int = 5037,
        device_manager: DeviceManager | None = None,
    ) -> None:
        self.device_id = device_id
        self.host = host
        self.port = port
        self.device_manager = device_manager
        self._client: AdbClient | None = None
        self._device: AdbDevice | None = None
        self._screen_size: tuple[int, int] | None = None

    @property
    def client(self) -> AdbClient:
        """获取 ADB 客户端"""
        if self._client is None:
            self._client = AdbClient(host=self.host, port=self.port)
        return self._client

    @property
    def device(self) -> AdbDevice:
        """获取设备实例"""
        if self._device is None:
            self._device = self.client.device(self.device_id)
        return self._device

    @property
    def screen_size(self) -> tuple[int, int]:
        """获取屏幕尺寸 (width, height)"""
        if self._screen_size is None:
            self._screen_size = self._get_screen_size()
        return self._screen_size

    def _get_screen_size(self) -> tuple[int, int]:
        """从设备获取屏幕尺寸"""
        try:
            output = self.device.shell("wm size").strip()
            if "Physical size:" in output:
                size_str = output.split("Physical size:")[-1].strip()
                if "x" in size_str:
                    w, h = size_str.split("x")
                    return int(w), int(h)
        except Exception:
            pass
        return 1080, 1920

    def screenshot(self, scale: float = 1.0) -> bytes:
        """
        截取屏幕
        
        Args:
            scale: 缩放比例 (0.0-1.0)
            
        Returns:
            PNG 图像数据
        """
        # adbutils 的 screenshot() 返回 PIL Image 对象
        img = self.device.screenshot()
        
        # 如果需要缩放
        if scale < 1.0:
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 转换为 bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def screenshot_to_file(self, path: str | Path, scale: float = 1.0) -> Path:
        """截图并保存到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.screenshot(scale)
        path.write_bytes(data)
        
        return path

    def tap(self, x: int, y: int) -> bool:
        """
        点击坐标
        
        Args:
            x: 屏幕 X 坐标
            y: 屏幕 Y 坐标
        """
        try:
            self.device.shell(f"input tap {x} {y}")
            return True
        except Exception as e:
            print(f"点击失败: {e}")
            return False

    def tap_relative(self, x: float, y: float) -> bool:
        """
        相对坐标点击 (0.0-1.0 或 0-1000)
        
        Args:
            x: 相对 X 坐标
            y: 相对 Y 坐标
        """
        width, height = self.screen_size
        
        # 支持 0-1000 的坐标系统
        if x > 1 or y > 1:
            abs_x = int(x / 1000 * width)
            abs_y = int(y / 1000 * height)
        else:
            abs_x = int(x * width)
            abs_y = int(y * height)
        
        return self.tap(abs_x, abs_y)

    def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """长按"""
        try:
            # 使用 swipe 模拟长按
            self.device.shell(f"input swipe {x} {y} {x} {y} {duration}")
            return True
        except Exception as e:
            print(f"长按失败: {e}")
            return False

    def double_tap(self, x: int, y: int, interval: float = 0.1) -> bool:
        """双击"""
        try:
            self.tap(x, y)
            import time
            time.sleep(interval)
            self.tap(x, y)
            return True
        except Exception as e:
            print(f"双击失败: {e}")
            return False

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: int = 300,
    ) -> bool:
        """滑动"""
        try:
            self.device.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")
            return True
        except Exception as e:
            print(f"滑动失败: {e}")
            return False

    def swipe_up(self, distance: float = 0.5, duration: int = 300) -> bool:
        """向上滑动"""
        width, height = self.screen_size
        x = width // 2
        y1 = int(height * 0.7)
        y2 = int(height * (0.7 - distance))
        return self.swipe(x, y1, x, y2, duration)

    def swipe_down(self, distance: float = 0.5, duration: int = 300) -> bool:
        """向下滑动"""
        width, height = self.screen_size
        x = width // 2
        y1 = int(height * 0.3)
        y2 = int(height * (0.3 + distance))
        return self.swipe(x, y1, x, y2, duration)

    def swipe_left(self, distance: float = 0.5, duration: int = 300) -> bool:
        """向左滑动"""
        width, height = self.screen_size
        y = height // 2
        x1 = int(width * 0.8)
        x2 = int(width * (0.8 - distance))
        return self.swipe(x1, y, x2, y, duration)

    def swipe_right(self, distance: float = 0.5, duration: int = 300) -> bool:
        """向右滑动"""
        width, height = self.screen_size
        y = height // 2
        x1 = int(width * 0.2)
        x2 = int(width * (0.2 + distance))
        return self.swipe(x1, y, x2, y, duration)

    def input_text(self, text: str) -> bool:
        """
        输入文本
        
        注意：对于中文输入，建议使用 ADBKeyboard
        """
        try:
            # 转义特殊字符
            escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
            escaped = escaped.replace(" ", "%s").replace("&", "\\&")
            self.device.shell(f'input text "{escaped}"')
            return True
        except Exception as e:
            print(f"输入失败: {e}")
            return False

    def input_text_adbime(self, text: str) -> bool:
        """使用 ADBKeyboard 输入文本（支持中文）"""
        try:
            # 广播方式输入，需要安装 ADBKeyboard
            import base64
            encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
            self.device.shell(
                f'am broadcast -a ADB_INPUT_B64 --es msg "{encoded}"'
            )
            return True
        except Exception as e:
            print(f"ADBKeyboard 输入失败: {e}")
            return False

    def press_key(self, keycode: int | str) -> bool:
        """按下按键"""
        try:
            self.device.shell(f"input keyevent {keycode}")
            return True
        except Exception as e:
            print(f"按键失败: {e}")
            return False

    def press_back(self) -> bool:
        """按下返回键"""
        return self.press_key(4)

    def press_home(self) -> bool:
        """按下 Home 键"""
        return self.press_key(3)

    def press_recent(self) -> bool:
        """按下最近任务键"""
        return self.press_key(187)

    def press_enter(self) -> bool:
        """按下回车键"""
        return self.press_key(66)

    def launch_app(self, package_name: str) -> bool:
        """启动应用"""
        try:
            # 方法1: 使用 am start 启动主 Activity
            result = self.device.shell(
                f"am start -n $(pm dump {package_name} | grep -A 1 'android.intent.action.MAIN' | grep -oP 'Activity\\.name=\\K[^ ]+' | head -1 || echo '{package_name}/.MainActivity')"
            )
            
            # 如果上面失败，尝试方法2: monkey
            if "Error" in result or not result.strip():
                self.device.shell(
                    f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1 2>/dev/null"
                )
            
            # 方法3: 尝试常见的启动方式
            # am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p <package>
            self.device.shell(
                f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER {package_name}"
            )
            
            return True
        except Exception as e:
            print(f"启动应用失败: {e}")
            return False

    def launch_app_simple(self, package_name: str) -> bool:
        """使用 monkey 简单启动应用"""
        try:
            self.device.shell(
                f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
            )
            return True
        except Exception as e:
            print(f"启动应用失败: {e}")
            return False

    def stop_app(self, package_name: str) -> bool:
        """停止应用"""
        try:
            self.device.shell(f"am force-stop {package_name}")
            return True
        except Exception as e:
            print(f"停止应用失败: {e}")
            return False

    def get_current_app(self) -> str | None:
        """获取当前前台应用包名"""
        try:
            output = self.device.shell(
                "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"
            ).strip()
            
            # 解析输出获取包名
            for line in output.split("\n"):
                if "mCurrentFocus" in line or "mFocusedApp" in line:
                    # 格式通常是 ... com.package.name/...
                    import re
                    match = re.search(r"(\w+(\.\w+)+)/", line)
                    if match:
                        return match.group(1)
        except Exception:
            pass
        return None

    def get_current_activity(self) -> tuple[str, str] | None:
        """获取当前 Activity (package, activity)"""
        try:
            output = self.device.shell(
                "dumpsys window | grep mCurrentFocus"
            ).strip()
            
            import re
            match = re.search(r"(\w+(\.\w+)+)/(\S+)", output)
            if match:
                return match.group(1), match.group(3)
        except Exception:
            pass
        return None

    async def wait(self, seconds: float) -> None:
        """异步等待"""
        await asyncio.sleep(seconds)
