import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_file):
    """Налаштовує RotatingFileHandler для логування"""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("telegram_sender")
    logger.setLevel(logging.DEBUG)

    # Уникаємо дублювання хендлерів при повторному запуску в debug-сесії.
    logger.handlers.clear()

    handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
