# 🤖 Telegram Invite Bot

Бот выдаёт **одноразовые** ссылки для вступления в чат после прохождения математической капчи.

## Как работает

1. Пользователь отправляет `/start`
2. Бот показывает математический пример с 4 вариантами ответа (кнопки)
3. При правильном ответе — бот создаёт одноразовую инвайт-ссылку через Telegram API
4. Ссылка работает только для **одного** входа
5. При 3 неверных попытках — сессия сбрасывается

---

## Установка и запуск

### 1. Клонируй / скачай файлы

```
tg_invite_bot/
├── bot.py
├── config.py
└── requirements.txt
```

### 2. Установи зависимости

```bash
pip install -r requirements.txt
```

### 3. Настрой config.py (или переменные окружения)

| Параметр   | Описание                                        |
|------------|-------------------------------------------------|
| `BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather)  |
| `CHAT_ID`  | ID чата (например `-1001234567890`)             |

**Как получить CHAT_ID:**
- Добавь [@userinfobot](https://t.me/userinfobot) в нужный чат и напиши `/start`
- Или перешли любое сообщение из чата боту [@getidsbot](https://t.me/getidsbot)

### 4. Сделай бота администратором чата

Бот должен быть **администратором** целевого чата с правом:
- ✅ Приглашать пользователей (Invite Users / Add Members)

### 5. Запусти бота

```bash
python bot.py
```

Или через переменные окружения:

```bash
BOT_TOKEN=123456:ABC... CHAT_ID=-1001234567890 python bot.py
```

---

## Деплой (опционально)

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t invite-bot .
docker run -d \
  -e BOT_TOKEN=ваш_токен \
  -e CHAT_ID=ваш_chat_id \
  invite-bot
```

### systemd (Linux сервер)

```ini
[Unit]
Description=Telegram Invite Bot
After=network.target

[Service]
WorkingDirectory=/opt/tg_invite_bot
Environment=BOT_TOKEN=ваш_токен
Environment=CHAT_ID=ваш_chat_id
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
