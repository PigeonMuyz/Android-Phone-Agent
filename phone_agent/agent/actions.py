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
    DRAG = "Drag"
    TYPE = "Type"
    TAP_AND_TYPE = "TapAndType"
    LAUNCH = "Launch"
    KEY_PRESS = "KeyPress"
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
            ActionType.DRAG: self._handle_drag,
            ActionType.TYPE: self._handle_type,
            ActionType.TAP_AND_TYPE: self._handle_tap_and_type,
            ActionType.LAUNCH: self._handle_launch,
            ActionType.KEY_PRESS: self._handle_key_press,
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
            element: [x, y] 相对坐标 (0-1000)

        Returns:
            (abs_x, abs_y) 绝对像素坐标
        """
        width, height = self.device.screen_size
        x = int(element[0] / 1000 * width)
        y = int(element[1] / 1000 * height)
        return x, y

    def _handle_tap(self, params: dict) -> ActionResult:
        """处理点击"""
        element = params.get("element", [500, 500])
        x, y = self._get_coords(element)
        
        # 检查是否是长按
        if params.get("long_press", False):
            duration = params.get("duration", 1000)  # 默认 1 秒
            if self.device.long_press(x, y, duration):
                return ActionResult(True, False, f"长按 ({x}, {y}) {duration}ms")
            return ActionResult(False, False, "长按失败")

        if self.device.tap(x, y):
            return ActionResult(True, False, f"点击 ({x}, {y})")
        return ActionResult(False, False, "点击失败")

    def _handle_swipe(self, params: dict) -> ActionResult:
        """处理滑动"""
        element = params.get("element")
        direction = params.get("direction", "up")

        if element and len(element) >= 4:
            # 使用 [x1, y1, x2, y2] 相对坐标 (0-1000)
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

    def _handle_drag(self, params: dict) -> ActionResult:
        """处理拖拽"""
        start = params.get("start", [500, 500])
        end = params.get("end", [500, 500])
        duration = params.get("duration", 1000)
        
        x1, y1 = self._get_coords(start)
        x2, y2 = self._get_coords(end)
        
        if self.device.swipe(x1, y1, x2, y2, duration):
            return ActionResult(True, False, f"拖拽 ({x1},{y1}) -> ({x2},{y2}) {duration}ms")
        return ActionResult(False, False, "拖拽失败")

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

    def _handle_tap_and_type(self, params: dict) -> ActionResult:
        """处理点击并输入（组合动作）"""
        element = params.get("element", [500, 500])
        text = params.get("text", "")
        clear = params.get("clear", False)
        
        if not text:
            return ActionResult(False, False, "缺少输入文本")
        
        x, y = self._get_coords(element)
        
        # 1. 先点击输入框
        if not self.device.tap(x, y):
            return ActionResult(False, False, "点击输入框失败")
        
        import time
        time.sleep(0.5)  # 等待输入框聚焦
        
        # 2. 可选：清空现有内容
        if clear:
            # 全选并删除
            self.device.press_key(123)  # KEYCODE_MOVE_END
            time.sleep(0.1)
            # 发送多个删除键
            for _ in range(50):  # 删除最多 50 个字符
                self.device.press_key(67)  # KEYCODE_DEL
        
        # 3. 输入文本
        if self.device.input_text_adbime(text) or self.device.input_text(text):
            return ActionResult(True, False, f"点击({x},{y})并输入: {text[:20]}...")
        
        return ActionResult(False, False, "输入文本失败")

    def _handle_launch(self, params: dict) -> ActionResult:
        """处理启动应用"""
        # 优先使用 app_name（应用中文名）
        app_name = params.get("app_name", "")
        package = params.get("package", "")
        
        if app_name:
            # 根据应用名查找包名
            package = self._find_package_by_name(app_name)
            if not package:
                return ActionResult(False, False, f"找不到应用: {app_name}")
        
        if not package:
            return ActionResult(False, False, "缺少 app_name 或 package 参数")

        if self.device.launch_app(package):
            display = f"{app_name} ({package})" if app_name else package
            return ActionResult(True, False, f"启动: {display}")
        display = f"{app_name} ({package})" if app_name else package
        return ActionResult(False, False, f"启动失败: {display}")

    def _find_package_by_name(self, app_name: str) -> str | None:
        """根据应用名称查找包名"""
        # 1. 先查静态映射表
        app_map = {
            "微信": "com.tencent.mm",
            "QQ": "com.tencent.mobileqq",
            "淘宝": "com.taobao.taobao",
            "京东": "com.jingdong.app.mall",
            "拼多多": "com.xunmeng.pinduoduo",
            "抖音": "com.ss.android.ugc.aweme",
            "快手": "com.smile.gifmaker",
            "美团": "com.sankuai.meituan",
            "饿了么": "com.ele.me",
            "支付宝": "com.eg.android.AlipayGphone",
            "高德地图": "com.autonavi.minimap",
            "百度地图": "com.baidu.BaiduMap",
            "滴滴": "com.sdu.didi.psnger",
            "网易云音乐": "com.netease.cloudmusic",
            "QQ音乐": "com.tencent.qqmusic",
            "爱奇艺": "com.qiyi.video",
            "腾讯视频": "com.tencent.qqlive",
            "优酷": "com.youku.phone",
            "哔哩哔哩": "tv.danmaku.bili",
            "B站": "tv.danmaku.bili",
            "小红书": "com.xingin.xhs",
            "知乎": "com.zhihu.android",
            "微博": "com.sina.weibo",
            "今日头条": "com.ss.android.article.news",
            "携程": "ctrip.android.view",
            "飞猪": "com.taobao.trip",
            "12306": "com.MobileTicket",
            "设置": "com.android.settings",
            "相机": "com.android.camera",
            "相册": "com.android.gallery3d",
            "日历": "com.android.calendar",
            "时钟": "com.android.deskclock",
            "计算器": "com.android.calculator2",
            "文件管理": "com.android.fileexplorer",
            "应用商店": "com.android.vending",
        }
        
        if app_name in app_map:
            return app_map[app_name]
        
        # 2. 动态查询设备安装的应用
        return self._search_package_on_device(app_name)
    
    def _search_package_on_device(self, app_name: str) -> str | None:
        """在设备上搜索应用包名"""
        try:
            # 获取所有已安装应用的包名和标签
            # 使用 pm list packages -3 获取第三方应用
            output = self.device.device.shell("pm list packages -3")
            
            # 解析包名列表
            packages = []
            for line in output.strip().split("\n"):
                if line.startswith("package:"):
                    pkg = line.replace("package:", "").strip()
                    packages.append(pkg)
            
            # 尝试关键词匹配
            # 将中文应用名转为可能的拼音/关键词
            keywords = self._extract_keywords(app_name)
            
            for pkg in packages:
                pkg_lower = pkg.lower()
                for keyword in keywords:
                    if keyword.lower() in pkg_lower:
                        return pkg
            
            return None
        except Exception:
            return None
    
    def _extract_keywords(self, app_name: str) -> list[str]:
        """从应用名提取可能的匹配关键词"""
        keywords = [app_name]
        
        # 常见游戏/应用的关键词映射
        keyword_map = {
            "剑网3": ["jx3", "jianwang", "seasun"],
            "剑网3无界": ["jx3", "jianwang", "seasun", "wujie"],
            "王者荣耀": ["sgame", "honor", "kings"],
            "原神": ["genshin", "mihoyo"],
            "崩坏": ["honkai", "mihoyo", "bh3"],
            "阴阳师": ["onmyoji", "netease"],
            "明日方舟": ["arknights", "hypergryph"],
            "和平精英": ["pubg", "tencent", "peacekeeper"],
            "英雄联盟": ["lol", "league", "tencent"],
            "穿越火线": ["crossfire", "cf"],
        }
        
        for name, kws in keyword_map.items():
            if name in app_name:
                keywords.extend(kws)
        
        # 添加拼音首字母（简单处理）
        # 例如："剑网3无界" 的部分可能是 jw3
        
        return keywords

    def _handle_key_press(self, params: dict) -> ActionResult:
        """处理物理按键"""
        key = params.get("key", "")
        if not key:
            return ActionResult(False, False, "缺少 key 参数")
        
        # 按键映射
        key_map = {
            "enter": 66,      # KEYCODE_ENTER
            "delete": 67,     # KEYCODE_DEL
            "volume_up": 24,  # KEYCODE_VOLUME_UP
            "volume_down": 25,  # KEYCODE_VOLUME_DOWN
            "app_switch": 187,  # KEYCODE_APP_SWITCH
            "snapshot": 120,  # KEYCODE_SYSRQ (screenshot)
        }
        
        keycode = key_map.get(key.lower())
        if keycode is None:
            return ActionResult(False, False, f"未知按键: {key}")
        
        if self.device.press_key(keycode):
            return ActionResult(True, False, f"按键: {key}")
        return ActionResult(False, False, f"按键失败: {key}")

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
        seconds = params.get("seconds", 5)  # 默认 5 秒
        # 限制在 1-30 秒范围
        seconds = max(1, min(30, seconds))
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
