import asyncio
import logging
import os
from pathlib import Path

from mega import Mega
from app.constants.paths import ARCHIVE_DIR
from app.config import settings
from app.constants.settings import MEGA_UPLOAD_INTERVAL_SECONDS

logger = logging.getLogger(__name__)


def upload_archives_to_mega():
    """
    Загружает ZIP-архивы из директории ARCHIVE_DIR в облако Mega.
    После успешной загрузки удаляет локальные файлы.
    """
    logger.info('🔐 Подключаемся к Mega...')
    mega = Mega()
    try:
        m = mega.login(settings.mega_email, settings.mega_password)
    except Exception as e:
        logger.error(f'❌ Ошибка входа в Mega: {e}')
        return

    archive_dir = Path(ARCHIVE_DIR)
    zip_files = list(archive_dir.glob('*.zip'))

    if not zip_files:
        logger.info('📂 Нет архивов для загрузки')
        return

    for file_path in zip_files:
        try:
            logger.info(f'📤 Загружаем: {file_path.name}')
            m.upload(file_path)
            os.remove(file_path)
            logger.info(f'✅ Загружено и удалено: {file_path.name}')
        except Exception as e:
            logger.warning(f'⚠️ Ошибка при загрузке {file_path.name}: {e}')


async def run_mega_uploader_loop():
    """
    Циклично проверяет наличие архивов и отправляет их на Mega
    с интервалом MEGA_UPLOAD_INTERVAL_SECONDS.
    """
    while True:
        logger.info('🚚 Отправка архивов на Mega...')
        upload_archives_to_mega()
        await asyncio.sleep(MEGA_UPLOAD_INTERVAL_SECONDS)
