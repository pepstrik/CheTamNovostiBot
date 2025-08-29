# CheTamNovostiBot 🎙️

Telegram-бот подкаста «Чё там новости»: поиск/случайный эпизод, авто-постинги и интеграция с RSS.

## Основные функции
- Поиск по эпизодам, краткие описания, кнопки c платформами
- Кэширование RSS и планирование задач (JobQueue)
- Автопостинг новых выпусков в канал/подписчикам
- База пользователей (aiosqlite)

## Технологии
Python · python-telegram-bot v20 · aiosqlite · feedparser · GitHub Actions

## Запуск локально
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.py.example config.py  # заполните токены и chat_id
python CheTamNovosti.py
```

## Roadmap
- [ ] /random: случайный эпизод
- [ ] Dockerfile + deploy guide
- [ ] Мониторинг ошибок/логов
