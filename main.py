#!/usr/bin/env python3
"""
Telegram Message Sender via RabbitMQ

Використання:
    python main.py --env /path/to/.env --log /path/to/app.log
    python main.py  # Uses .env and app.log from project dir
"""

import argparse
import asyncio
import sys

from app.consumers.message_consumer import MessageConsumer
from app.core.config import Config
from app.core.logger import setup_logger
from app.services.telegram_sender import TelegramSender


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Message Sender via RabbitMQ"
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="Шлях до .env файлу (за замовчуванням: .env у проекті)"
    )
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Шлях до файлу логу (за замовчуванням: ./app.log у проекті)"
    )
    
    args = parser.parse_args()
    
    try:
        # Завантажуємо конфіг
        config = Config(env_file=args.env, log_file=args.log)
        print(f"[CONFIG] .env завантажено, RabbitMQ: {config.rabbitmq_host}:{config.rabbitmq_port}")
        
        # Налаштовуємо логування
        logger = setup_logger(config.log_file)
        logger.info("=" * 60)
        logger.info("Запуск Telegram Message Sender")
        logger.info(f"RabbitMQ: {config.rabbitmq_host}:{config.rabbitmq_port}")
        logger.info(f"Черга: {config.rabbitmq_queue}")
        logger.info(f"Лог файл: {config.log_file}")
        logger.info("=" * 60)
        
        # Ініціалізуємо Telegram sender
        sender = TelegramSender(config.telegram_bot_token)
        
        # Ініціалізуємо consumer
        consumer = MessageConsumer(config, sender, logger)
        
        # Запускаємо asyncio loop + pika consumer
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        consumer.start(loop)
    
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] Конфіг помилка: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] Завершено користувачем")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Неочікувана помилка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
