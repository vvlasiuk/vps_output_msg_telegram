import asyncio
import json
import threading
from logging import Logger
from typing import Optional

import pika

from app.services.telegram_sender import TelegramSender


class MessageConsumer:
    """RabbitMQ consumer з asyncio workers для кожного chat_id"""

    def __init__(self, config, sender: TelegramSender, logger: Logger):
        self.config = config
        self.sender = sender
        self.logger = logger

        self.queues = {}
        self.workers = {}
        self.workers_lock = asyncio.Lock()

        self.connection = None
        self.channel = None
        self.should_stop = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.logger.info("Запуск consumer...")

        pika_thread = threading.Thread(target=self._run_pika, daemon=True)
        pika_thread.start()

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.logger.info("Отримано сигнал завершення")
        finally:
            self.should_stop = True
            self._close_pika()
            loop.close()

    def _run_pika(self):
        try:
            creds = pika.PlainCredentials(
                self.config.rabbitmq_user,
                self.config.rabbitmq_password,
            )
            params = pika.ConnectionParameters(
                host=self.config.rabbitmq_host,
                port=self.config.rabbitmq_port,
                credentials=creds,
                virtual_host=self.config.rabbitmq_vhost,
                heartbeat=60,
                blocked_connection_timeout=300,
                connection_attempts=3,
                retry_delay=2,
            )

            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            self.channel.basic_qos(prefetch_count=1)

            self.logger.info(
                "Підключено до RabbitMQ, чекаю повідомлень у черзі: %s",
                self.config.rabbitmq_queue,
            )

            self.channel.basic_consume(
                queue=self.config.rabbitmq_queue,
                on_message_callback=self._on_message,
                auto_ack=False,
            )
            self.channel.start_consuming()

        except Exception as exc:
            self.logger.error("Помилка pika: %s", exc)
        finally:
            self._close_pika()

    def _on_message(self, ch, method, properties, body):
        del properties
        try:
            message = json.loads(body.decode())
            destination = message.get("destination", {})
            chat_id = destination.get("chat_id")

            if not chat_id:
                self.logger.error("Повідомлення без chat_id: %s", message)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            if self.loop is None:
                self.logger.error("Event loop не ініціалізовано")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

            asyncio.run_coroutine_threadsafe(
                self._enqueue_message(str(chat_id), message),
                self.loop,
            )

            ch.basic_ack(delivery_tag=method.delivery_tag)
            self.logger.debug("Повідомлення для chat_id=%s в черзі", chat_id)

        except json.JSONDecodeError as exc:
            self.logger.error("Помилка парсингу JSON: %s", exc)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            self.logger.error("Помилка при обробці повідомлення: %s", exc)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    async def _enqueue_message(self, chat_id, message):
        if chat_id not in self.queues:
            self.queues[chat_id] = asyncio.Queue()
            async with self.workers_lock:
                if chat_id not in self.workers:
                    self.workers[chat_id] = asyncio.create_task(self._worker(chat_id))

        await self.queues[chat_id].put(message)

    async def _worker(self, chat_id):
        self.logger.info("Запущен worker для chat_id=%s", chat_id)
        queue = self.queues[chat_id]

        while not self.should_stop:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=5.0)
                await self._process_message(chat_id, message)
                queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                self.logger.info("Worker для chat_id=%s скасовано", chat_id)
                break
            except Exception as exc:
                self.logger.error("Помилка в worker для chat_id=%s: %s", chat_id, exc)

    async def _process_message(self, chat_id, message):
        try:
            msg_type = str(message.get("type", "text")).lower()
            content = message.get("content")


            # Якщо є тег 'keyboard', формуємо клавіатуру з його вмісту
            keyboard = message.get("keyboard")

            if msg_type in {"text", "emoji"}:
                if keyboard:
                    from app.services.telegram_sender import get_keyboard
                    reply_markup = get_keyboard(keyboard)
                    await self.sender.send_text(chat_id, content, reply_markup=reply_markup.to_dict())
                    self.logger.info("Повідомлення типу %s відправлено chat_id=%s з кастомною клавіатурою", msg_type, chat_id)
                else:
                    await self.sender.send_text(chat_id, content)
                    self.logger.info("Повідомлення типу %s відправлено chat_id=%s без клавіатури", msg_type, chat_id)
                return

            if msg_type == "photo":
                await self.sender.send_photo(
                    chat_id,
                    message.get("file_path"),
                    message.get("caption"),
                )
                self.logger.info("Фото відправлено chat_id=%s: %s", chat_id, message.get("file_path"))
                return

            if msg_type == "file":
                await self.sender.send_file(
                    chat_id,
                    message.get("file_path"),
                    message.get("caption"),
                )
                self.logger.info("Файл відправлено chat_id=%s: %s", chat_id, message.get("file_path"))
                return

            self.logger.warning("Невідомий тип повідомлення: %s", msg_type)

        except FileNotFoundError as exc:
            self.logger.error("Файл не знайдено для chat_id=%s: %s", chat_id, exc)
        except Exception as exc:
            self.logger.error("Помилка при відправці до chat_id=%s: %s", chat_id, exc)

    def _close_pika(self):
        try:
            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()
                self.channel.close()
        except Exception:
            pass

        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception:
            pass

        self.logger.info("RabbitMQ з'єднання закрито")
