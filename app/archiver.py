import asyncio
import logging
import os
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from app.constants.paths import EXPORT_PINNACLE_DIR, EXPORT_ANALYZER_DIR, ARCHIVE_DIR
from app.constants.settings import ARCHIVE_AGE_THRESHOLD, ARCHIVE_INTERVAL


logger = logging.getLogger(__name__)


def zip_and_cleanup_yesterdays_exports():
    """
    Архивирует и удаляет старые CSV-файлы из экспортных директорий.
    Создаёт ZIP-файл с временной меткой и переносит его в папку архивов.
    """
    threshold_time = datetime.utcnow() - timedelta(hours=ARCHIVE_AGE_THRESHOLD)
    timestamp_str = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')

    for source_dir in [EXPORT_PINNACLE_DIR, EXPORT_ANALYZER_DIR]:
        source_path = Path(source_dir)
        source_name = source_path.name

        files_to_archive = [
            file_path for file_path in source_path.glob('*.csv')
            if datetime.utcfromtimestamp(file_path.stat().st_mtime) < threshold_time
        ]

        if not files_to_archive:
            logger.info(
                f'📁 Нет файлов старше {ARCHIVE_AGE_THRESHOLD} часов в {source_name}, пропускаем')
            continue

        archive_name = f'{source_name}_{timestamp_str}.zip'
        archive_path = Path(ARCHIVE_DIR) / archive_name

        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_archive:
                zipf.write(file_path, arcname=file_path.name)
                logger.info(f'➕ Добавлен в архив: {file_path.name}')

        for file_path in files_to_archive:
            try:
                os.remove(file_path)
                logger.info(f'🗑️ Удалён: {file_path.name}')
            except Exception as e:
                logger.warning(f'❌ Ошибка при удалении {file_path.name}: {e}')

        logger.info(f'✅ Архив создан: {archive_path}')


async def run_archiver_loop():
    """
    Запускает бесконечный цикл проверки и архивации старых CSV-файлов.
    """
    while True:
        logger.info('📦 Запущен архиватор: проверка старых CSV-файлов...')
        zip_and_cleanup_yesterdays_exports()
        await asyncio.sleep(ARCHIVE_INTERVAL)
