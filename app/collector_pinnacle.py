import asyncio
import csv
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.csv_columns import CSV_PINNACLE_COLUMNS
from app.constants.paths import EXPORT_PINNACLE_DIR
from app.constants.settings import OUTDATED_THRESHOLD, EXPORT_INTERVAL_SECONDS
from app.db import SessionLocal
from app.models import LiveOddsParsed
from app.utils import format_filename

logger = logging.getLogger(__name__)


def expand_market_map(rows: list[LiveOddsParsed]) -> dict[str, dict[str, float]]:
    """
    Группирует данные по created_at (секунды) и преобразует их в формат для экспорта в CSV,
    включая Totals, Handicap, First/Second Team Totals и Games.
    """
    snapshot_dict = defaultdict(dict)

    # Временные мапы для Totals и других с линиями
    totals_map = defaultdict(list)
    handicap_map = defaultdict(list)
    ft_totals_map = defaultdict(list)
    st_totals_map = defaultdict(list)
    games_map = defaultdict(list)

    for row in rows:
        key = row.created_at.replace(microsecond=0).isoformat()

        try:
            line_value = float(row.line) if row.line is not None else 0.0
        except ValueError:
            line_value = 0.0

        market = row.market
        outcome = row.outcome

        if market == 'Totals':
            totals_map[key].append((line_value, outcome, row.value))
        elif market == 'Handicap':
            handicap_map[key].append((line_value, outcome, row.value))
        elif market == 'FirstTeamTotals':
            ft_totals_map[key].append((line_value, outcome, row.value))
        elif market == 'SecondTeamTotals':
            st_totals_map[key].append((line_value, outcome, row.value))
        elif market == 'Games':
            games_map[key].append((line_value, outcome, row.value))
        else:
            col_name = f'{market}_{outcome}'
            snapshot_dict[key][col_name] = row.value

    def fill_slots(target_dict, source_map, prefix, allowed_outcomes, max_lines=3):
        """
        Раскладывает значения с линиями по слотам, сортируя по значению линии.
        """
        for key, values in source_map.items():
            seen_lines = {}
            values.sort(key=lambda x: x[0])
            for line, outcome, value in values:
                if outcome not in allowed_outcomes:
                    continue
                slot = seen_lines.get(line)
                if slot is None:
                    slot = len(seen_lines) + 1
                    if slot > max_lines:
                        continue
                    seen_lines[line] = slot
                col_name = f'{prefix}_{slot}_{outcome}'
                target_dict[key][col_name] = value

    fill_slots(snapshot_dict, totals_map, 'Totals', {'WinMore', 'WinLess'})
    fill_slots(snapshot_dict, handicap_map, 'Handicap', {'Win1', 'Win2'})
    fill_slots(snapshot_dict, ft_totals_map, 'FirstTeamTotals', {'WinMore', 'WinLess'}, max_lines=2)
    fill_slots(snapshot_dict, st_totals_map, 'SecondTeamTotals', {'WinMore', 'WinLess'}, max_lines=2)
    fill_slots(snapshot_dict, games_map, 'Games', {'Win1', 'Win2', 'WinNone'}, max_lines=2)

    return snapshot_dict


async def collect_and_export_old_data():
    """
    Находит устаревшие матчи по данным от Pinnacle и экспортирует их в CSV.
    После экспорта удаляет данные матчи из базы.
    """
    now = datetime.utcnow()
    outdated_time = now - timedelta(hours=OUTDATED_THRESHOLD)

    async with SessionLocal() as session:
        match_ids = await find_stale_matches(session, outdated_time)

        for match_id in match_ids:
            await export_and_delete_match(session, match_id)


async def find_stale_matches(session: AsyncSession, outdated_time: datetime) -> list[int]:
    """
    Возвращает список матчей, которые не обновлялись дольше указанного времени.
    """
    subquery = (
        select(
            LiveOddsParsed.match_id,
            func.max(LiveOddsParsed.created_at).label('max_created_at')
        )
        .group_by(LiveOddsParsed.match_id)
        .subquery()
    )

    result = await session.execute(
        select(subquery.c.match_id)
        .where(subquery.c.max_created_at < outdated_time)
    )

    match_ids = [row[0] for row in result.all()]
    logger.info(f'🔍 Найдено {len(match_ids)} устаревших матчей для выгрузки')
    return match_ids


async def export_and_delete_match(session: AsyncSession, match_id: int):
    """
    Экспортирует данные по заданному матчу Pinnacle в CSV и удаляет их из базы.
    """
    logger.info(f'Обрабатываем матч {match_id}')
    result = await session.stream(
        select(LiveOddsParsed).where(LiveOddsParsed.match_id == match_id)
    )
    rows = []
    async for row in result.scalars():
        rows.append(row)

    if not rows:
        logger.warning(f'⚠️ Нет данных для матча {match_id}')
        return

    snapshot_dict = expand_market_map(rows)

    created_at_sample = rows[0].created_at
    home = rows[0].home_team or 'home'
    away = rows[0].away_team or 'away'
    sport = rows[0].sport_name or 'sport'
    file_name = format_filename(match_id, created_at_sample, home, away, sport)
    file_path = os.path.join(EXPORT_PINNACLE_DIR, file_name)

    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_PINNACLE_COLUMNS)
        writer.writeheader()

        for ts, row_data in sorted(snapshot_dict.items()):
            row = {col: 'null' for col in CSV_PINNACLE_COLUMNS}
            row['CreatedAt'] = ts
            row['homeName'] = home
            row['awayName'] = away
            row['HomeScore'] = rows[0].home_score or 0
            row['AwayScore'] = rows[0].away_score or 0

            for k, v in row_data.items():
                if k in row:
                    row[k] = 'null' if v is None else v

            writer.writerow(row)

    await session.execute(
        LiveOddsParsed.__table__.delete().where(LiveOddsParsed.match_id == match_id)
    )
    await session.commit()
    logger.info(f'✅ Матч {match_id} экспортирован и удалён')


async def run_pinnacle_collector_loop():
    """
    Цикл экспорта и удаления устаревших матчей Pinnacle.
    Выполняется с интервалом EXPORT_INTERVAL_SECONDS.
    """
    while True:
        await collect_and_export_old_data()
        await asyncio.sleep(EXPORT_INTERVAL_SECONDS)
