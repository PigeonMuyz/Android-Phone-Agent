"""Local OCR engine for keyboard detection."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from PIL import Image


@dataclass
class OCRResult:
    """OCR 识别结果"""

    keyboard_active: bool = False
    raw_text: str = ""


class OCREngine:
    """本地 OCR 引擎 - 使用 pytesseract"""

    def __init__(self) -> None:
        self._tesseract_available: bool | None = None

    def _check_tesseract(self) -> bool:
        """检查 tesseract 是否可用"""
        if self._tesseract_available is not None:
            return self._tesseract_available

        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._tesseract_available = True
        except Exception:
            self._tesseract_available = False

        return self._tesseract_available

    def recognize(self, image: bytes | Image.Image) -> OCRResult:
        """
        识别图像中的文字

        Args:
            image: PNG 图像数据或 PIL Image 对象

        Returns:
            OCRResult
        """
        if not self._check_tesseract():
            return OCRResult()

        import pytesseract

        # 转换为 PIL Image
        if isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
        else:
            img = image

        # ADB Keyboard 通知在屏幕底部
        width, height = img.size
        # 只识别底部区域（提高速度）
        bottom_region = img.crop((0, max(0, height - 150), width, height))

        try:
            text = pytesseract.image_to_string(bottom_region, lang='eng')
        except Exception:
            return OCRResult()

        keyboard_active = self._detect_keyboard_active(text)

        return OCRResult(
            keyboard_active=keyboard_active,
            raw_text=text,
        )

    def _detect_keyboard_active(self, text: str) -> bool:
        """检测 ADB Keyboard 是否激活"""
        # 匹配 "ADB Keyboard" 或类似文字
        patterns = [
            r"ADB\s*Keyboard",
            r"adb\s*keyboard",
            r"ADB\s*Input",
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def get_screen_context(self, image: bytes | Image.Image) -> str:
        """
        获取屏幕上下文描述（用于 Prompt）
        """
        result = self.recognize(image)

        if result.keyboard_active:
            return "📱 状态: 输入框已激活 (ADB Keyboard 已弹出，可以直接输入文本)"

        return ""
