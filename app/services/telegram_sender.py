import asyncio
from pathlib import Path

import requests

import json
from telegram import ReplyKeyboardMarkup, KeyboardButton

def load_menu_config(path="menu_config.json"):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Якщо немає реального файлу, пробуємо зразок
        with open("menu_config.example.json", encoding="utf-8") as f:
            return json.load(f)

def get_keyboard(keyboard_dict):
    return ReplyKeyboardMarkup(
        keyboard=keyboard_dict["keyboard"],
        resize_keyboard=keyboard_dict.get("resize_keyboard", True),
        one_time_keyboard=keyboard_dict.get("one_time_keyboard", False),
        is_persistent=keyboard_dict.get("is_persistent", True)
    )


class TelegramSender:

    """Асинхронна відправка повідомлень в Telegram"""

    BASE_URL = "https://api.telegram.org/bot"
    TIMEOUT = 30

    def __init__(self, token):
        self.api_url = f"{self.BASE_URL}{token}"

    async def send_text(self, chat_id, text, reply_markup=None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self._request(
            "sendMessage",
            **payload
        )

    async def send_photo(self, chat_id, file_path, caption=None):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Фото не знайдено: {path}")

        with path.open("rb") as file_obj:
            files = {"photo": file_obj}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            return await self._request_multipart("sendPhoto", files=files, data=data)

    async def send_file(self, chat_id, file_path, caption=None):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл не знайдено: {path}")

        with path.open("rb") as file_obj:
            files = {"document": file_obj}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            return await self._request_multipart("sendDocument", files=files, data=data)

    async def _request(self, method, **payload):
        url = f"{self.api_url}/{method}"
        loop = asyncio.get_running_loop()

        def send():
            response = requests.post(url, json=payload, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.json()

        try:
            return await loop.run_in_executor(None, send)
        except requests.RequestException as exc:
            raise RuntimeError(f"Telegram API error: {exc}") from exc

    async def _request_multipart(self, method, files, data):
        url = f"{self.api_url}/{method}"
        loop = asyncio.get_running_loop()

        def send():
            response = requests.post(url, files=files, data=data, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.json()

        try:
            return await loop.run_in_executor(None, send)
        except requests.RequestException as exc:
            raise RuntimeError(f"Telegram API error: {exc}") from exc
