"""Multi-device manager using adbutils."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from adbutils import AdbClient, AdbDevice
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from phone_agent.config import Settings


class DeviceState(str, Enum):
    """设备状态"""

    ONLINE = "online"  # 在线，可用
    OFFLINE = "offline"  # 离线
    BUSY = "busy"  # 正在执行任务
    UNAUTHORIZED = "unauthorized"  # 未授权


class AppInfo(BaseModel):
    """应用信息"""

    package_name: str = Field(description="包名")
    app_name: str | None = Field(default=None, description="应用名称")
    version: str | None = Field(default=None, description="版本号")


class DeviceInfo(BaseModel):
    """设备信息"""

    device_id: str = Field(description="设备序列号")
    state: DeviceState = Field(default=DeviceState.ONLINE)
    model: str | None = Field(default=None, description="设备型号")
    brand: str | None = Field(default=None, description="品牌")
    android_version: str | None = Field(default=None, description="Android 版本")
    sdk_version: int | None = Field(default=None, description="SDK 版本")
    screen_width: int | None = Field(default=None, description="屏幕宽度")
    screen_height: int | None = Field(default=None, description="屏幕高度")
    current_task_id: str | None = Field(default=None, description="当前任务 ID")


class DeviceManager:
    """多设备管理器"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5037,
        cache_dir: Path | None = None,
        cache_ttl: int = 3600,
    ) -> None:
        self.host = host
        self.port = port
        self.cache_dir = cache_dir or Path(".cache/apps")
        self.cache_ttl = cache_ttl
        self._client: AdbClient | None = None
        self._devices: dict[str, DeviceInfo] = {}
        self._lock = asyncio.Lock()

    @property
    def client(self) -> AdbClient:
        """获取 ADB 客户端"""
        if self._client is None:
            self._client = AdbClient(host=self.host, port=self.port)
        return self._client

    def scan_devices(self) -> list[DeviceInfo]:
        """扫描所有连接的设备"""
        devices: list[DeviceInfo] = []

        for adb_device in self.client.device_list():
            device_info = self._get_device_info(adb_device)
            devices.append(device_info)
            self._devices[device_info.device_id] = device_info

        return devices

    def _get_device_info(self, adb_device: AdbDevice) -> DeviceInfo:
        """获取设备详细信息"""
        serial = adb_device.serial

        # 获取设备属性
        try:
            props = adb_device.shell("getprop").strip()
            prop_dict = self._parse_props(props)

            model = prop_dict.get("ro.product.model")
            brand = prop_dict.get("ro.product.brand")
            android_version = prop_dict.get("ro.build.version.release")
            sdk_version_str = prop_dict.get("ro.build.version.sdk")
            sdk_version = int(sdk_version_str) if sdk_version_str else None

            # 获取屏幕尺寸
            screen_width, screen_height = self._get_screen_size(adb_device)

            return DeviceInfo(
                device_id=serial,
                state=DeviceState.ONLINE,
                model=model,
                brand=brand,
                android_version=android_version,
                sdk_version=sdk_version,
                screen_width=screen_width,
                screen_height=screen_height,
            )
        except Exception:
            return DeviceInfo(device_id=serial, state=DeviceState.OFFLINE)

    def _parse_props(self, props_output: str) -> dict[str, str]:
        """解析 getprop 输出"""
        result: dict[str, str] = {}
        for line in props_output.split("\n"):
            line = line.strip()
            if line.startswith("[") and "]: [" in line:
                # [key]: [value]
                key_end = line.index("]: [")
                key = line[1:key_end]
                value = line[key_end + 4 : -1]
                result[key] = value
        return result

    def _get_screen_size(self, adb_device: AdbDevice) -> tuple[int, int]:
        """获取屏幕尺寸"""
        try:
            output = adb_device.shell("wm size").strip()
            # Physical size: 1080x2340
            if "Physical size:" in output:
                size_str = output.split("Physical size:")[-1].strip()
                if "x" in size_str:
                    w, h = size_str.split("x")
                    return int(w), int(h)
        except Exception:
            pass
        return 1080, 1920  # 默认尺寸

    def get_device(self, device_id: str) -> DeviceInfo | None:
        """获取指定设备信息"""
        return self._devices.get(device_id)

    def get_available_devices(self) -> list[DeviceInfo]:
        """获取所有可用（在线且空闲）的设备"""
        return [d for d in self._devices.values() if d.state == DeviceState.ONLINE]

    async def acquire_device(self, device_id: str, task_id: str) -> bool:
        """获取设备使用权（标记为 BUSY）"""
        async with self._lock:
            device = self._devices.get(device_id)
            if device and device.state == DeviceState.ONLINE:
                device.state = DeviceState.BUSY
                device.current_task_id = task_id
                return True
            return False

    async def release_device(self, device_id: str) -> None:
        """释放设备（标记为 ONLINE）"""
        async with self._lock:
            device = self._devices.get(device_id)
            if device:
                device.state = DeviceState.ONLINE
                device.current_task_id = None

    def get_installed_apps(self, device_id: str, use_cache: bool = True) -> list[AppInfo]:
        """获取设备上安装的应用列表（支持缓存）"""
        cache_file = self.cache_dir / f"{device_id}_apps.json"

        # 尝试从缓存读取
        if use_cache and cache_file.exists():
            try:
                cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
                cache_time = datetime.fromisoformat(cache_data["timestamp"])
                if (datetime.now() - cache_time).total_seconds() < self.cache_ttl:
                    return [AppInfo(**app) for app in cache_data["apps"]]
            except Exception:
                pass

        # 从设备获取
        adb_device = self.client.device(device_id)
        apps = self._fetch_installed_apps(adb_device)

        # 写入缓存
        self._save_apps_cache(device_id, apps)

        return apps

    def _fetch_installed_apps(self, adb_device: AdbDevice) -> list[AppInfo]:
        """从设备获取已安装应用"""
        apps: list[AppInfo] = []

        try:
            # 获取第三方应用
            output = adb_device.shell("pm list packages -3").strip()
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("package:"):
                    package_name = line[8:]
                    # 尝试获取应用名称
                    app_name = self._get_app_name(adb_device, package_name)
                    apps.append(AppInfo(package_name=package_name, app_name=app_name))
        except Exception as e:
            print(f"获取应用列表失败: {e}")

        return apps

    def _get_app_name(self, adb_device: AdbDevice, package_name: str) -> str | None:
        """获取应用显示名称"""
        try:
            # 使用 dumpsys 获取应用标签
            output = adb_device.shell(
                f"dumpsys package {package_name} | grep -E 'applicationInfo|labelRes'"
            )
            # 简化处理，返回 None 让后续用包名
            return None
        except Exception:
            return None

    def _save_apps_cache(self, device_id: str, apps: list[AppInfo]) -> None:
        """保存应用列表缓存"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / f"{device_id}_apps.json"

        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "device_id": device_id,
            "apps": [app.model_dump() for app in apps],
        }

        cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def find_app_by_name(
        self, device_id: str, keyword: str, use_cache: bool = True
    ) -> AppInfo | None:
        """通过关键词搜索应用"""
        apps = self.get_installed_apps(device_id, use_cache)
        keyword_lower = keyword.lower()

        for app in apps:
            if keyword_lower in app.package_name.lower():
                return app
            if app.app_name and keyword_lower in app.app_name.lower():
                return app

        return None
