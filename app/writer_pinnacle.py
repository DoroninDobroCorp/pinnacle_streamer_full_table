import logging
from typing import Any

from app.db import SessionLocal
from app.models import LiveOddsParsed
from app.utils import generate_pinnacle_key_hash, safe_parse_iso
from sqlalchemy.ext.asyncio import AsyncSession


ALLOWED_SPORTS = ('Soccer', 'Tennis')
logger = logging.getLogger(__name__)


async def write_to_storage(messages: list[dict[str, Any]]):
    """
    Обрабатывает список сообщений от Pinnacle, преобразует их в объекты LiveOddsParsed
    и сохраняет в базу данных. Если в сообщении нет коэффициентов, добавляется строка-заглушка
    с мета-информацией (команды, счёт, время).

    :param messages: Список словарей с сообщениями от Pinnacle
    """
    if not messages:
        return

    # logger.info(f'🔽 Обрабатываем {len(messages)} сообщений для записи')
    parsed_rows = []

    for msg in messages:
        try:
            match_id = int(msg.get('MatchId', 0))
            periods = msg.get('Periods') or []
            created_at = msg.get('CreatedAt')
            home_name = msg.get('homeName')
            away_name = msg.get('awayName')
            sport_name = msg.get('SportName')
            home_score = msg.get('HomeScore', 0)
            away_score = msg.get('AwayScore', 0)

            created_at_dt = safe_parse_iso(created_at)
            added = False

            for period_index, period_data in enumerate(periods):
                period_label = str(period_index + 1)

                for market, outcomes in period_data.items():
                    if not isinstance(outcomes, dict):
                        continue

                    for line, outcome_values in outcomes.items():
                        if not isinstance(outcome_values, dict):
                            continue

                        line_str = str(line)

                        for outcome, value_data in outcome_values.items():
                            value = value_data.get('value') if isinstance(
                                value_data, dict) else None
                            try:
                                value = float(value)
                            except (TypeError, ValueError):
                                continue

                            key_hash = generate_pinnacle_key_hash(
                                match_id, period_label, market, outcome
                            )

                            parsed_rows.append(LiveOddsParsed(
                                match_id=match_id,
                                period=period_label,
                                market=market,
                                outcome=outcome,
                                line=line_str,
                                value=value,
                                created_at=created_at_dt,
                                key_hash=key_hash,
                                home_team=home_name,
                                away_team=away_name,
                                sport_name=sport_name,
                            ))
                            added = True

            # если нет коэффициентов — пишем заглушку с мета-инфой
            if not added:
                key_hash = generate_pinnacle_key_hash(match_id, '0', 'meta', 'meta')
                parsed_rows.append(LiveOddsParsed(
                    match_id=match_id,
                    period='0',
                    market='meta',
                    outcome='meta',
                    line='',
                    value=None,
                    created_at=created_at_dt,
                    key_hash=key_hash,
                    home_team=home_name,
                    away_team=away_name,
                    sport_name=sport_name,
                    home_score=home_score,
                    away_score=away_score,
                ))

        except Exception as e:
            logger.warning(f'❌ Ошибка при разборе сообщения:\n{msg}\n🧨 {e}')

    if parsed_rows:
        async with SessionLocal() as session:
            await save_parsed_rows(session, parsed_rows)


async def save_parsed_rows(session: AsyncSession, rows: list[LiveOddsParsed]):
    """
    Сохраняет список объектов LiveOddsParsed в базу данных через переданную сессию.

    :param session: Асинхронная сессия SQLAlchemy
    :param rows: Список строк для записи
    """
    session.add_all(rows)
    await session.commit()
    logger.info(f'✅ Сохранили {len(rows)} строк от пинакл')
