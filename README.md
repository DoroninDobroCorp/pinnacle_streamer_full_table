# 📡 Pinnacle Streamer

**Pinnacle Streamer** — это микросервис, который подключается к WebSocket-источникам, собирает live-коэффициенты и анализаторские данные, сохраняет их в базу данных, периодически выгружает в CSV и архивирует, а затем загружает на облако Mega.

## 🚀 Основные возможности

- Подключение к WebSocket-источникам (Pinnacle, Analyzer)
- Сбор live-коэффициентов и аналитических данных
- Хранение в PostgreSQL
- Выгрузка старых матчей в CSV (структурированный шаблон)
- Архивация и удаление выгруженных файлов
- Загрузка архивов на Mega.nz
о
---

## 📁 Структура проекта

pinnacle_streamer/ 
│ ├── app/ # Основная логика микросервиса 
│ ├── constants/ # Константы путей, настроек, шаблонов CSV 
│ ├── aggregator.py # Буферизация входящих сообщений 
│ ├── archiver.py # Архивация старых CSV-файлов 
│ ├── collector_analyzer.py # Выгрузка данных анализатора 
│ ├── collector_pinnacle.py # Выгрузка данных Pinnacle 
│ ├── config.py # Загрузка конфигурации из .env 
│ ├── db.py # Подключение к базе данных 
│ ├── models.py # SQLAlchemy модели 
│ ├── uploader_to_mega.py # Загрузка архивов на Mega 
│ ├── utils.py # Утилиты (хэши, парсинг дат, логирование) 
│ ├── websocket_client.py # WebSocket-клиент 
│ ├── writer_analyzer.py # Парсинг и запись данных анализатора 
│ └── writer_pinnacle.py # Парсинг и запись данных Pinnacle 
│ ├── scripts/ 
│ └── run_pinnacle_streamer.py # Точка входа 
│ ├── exports/ # Папка для выгрузок 
│ ├── analyzer/ # CSV-файлы анализатора 
│ ├── pinnacle/ # CSV-файлы Pinnacle 
│ └── archives/ # Архивы .zip 
│ ├── alembic/ # Миграции базы данных 
├── .env # Конфигурация окружения (не в репозитории) 
├── Dockerfile # Образ для запуска микросервиса 
├── docker-compose.yml # Конфигурация docker-compose 
├── requirements.txt # Зависимости проекта 
└── README.md # Документация (этот файл)

---

## 🐳 Запуск проекта через Docker

### 🔧 1. Собери контейнеры
```bash
   docker compose up --build  
```

### 🚀 2. Запусти сервис
```bash
   docker compose run --rm app python -m scripts.run_pinnacle_streamer
```
Контейнер запустит WebSocket-клиент, сбор данных, экспорт CSV и загрузку архивов на Mega.

## 🔐 Переменные окружения
Скопируй `.env.example` в `.env` (файл `.env` в git не попадает) и заполни своими значениями:


WS_PINNACLE_URL=ws://...
WS_ANALYZER_URL=ws://...
FILTER_NAME=main
SPORTS=Soccer,Tennis
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname
MEGA_EMAIL=your_email@example.com
MEGA_PASSWORD=your_password


🧠 Примечания
Все входящие сообщения буферизуются и группируются по времени перед записью.

Коэффициенты записываются построчно с key_hash, чтобы избежать дублирования.

Экспорт по шаблону CSV_PINNACLE_COLUMNS или CSV_ANALYZER_COLUMNS.

Архивы создаются раз в 2 часа и заливаются на Mega.
