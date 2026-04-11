import os
from pathlib import Path

from dotenv import load_dotenv


class Config:
    """Завантажує конфіг з .env файлу (параметр або проект)"""

    def __init__(self, env_file=None, log_file=None):
        self.project_dir = Path(__file__).resolve().parents[2]

        if env_file:
            env_path = Path(env_file)
            if not env_path.exists():
                raise FileNotFoundError(f"ENV файл не знайдений: {env_file}")
            load_dotenv(env_path)
        else:
            load_dotenv(self.project_dir / ".env")

        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")

        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        self.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", 5672))
        self.rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        self.rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
        self.rabbitmq_vhost = os.getenv("RABBITMQ_VHOST", "/")
        self.rabbitmq_queue = os.getenv("RABBITMQ_QUEUE")
        if not self.rabbitmq_queue:
            raise ValueError("RABBITMQ_QUEUE не задан в .env")

        self.log_file = Path(log_file) if log_file else self.project_dir / "app.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
