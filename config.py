import os

# ─── Обязательные настройки ────────────────────────────────────────────────────
# Токен бота от @BotFather
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ID чата, куда бот будет создавать инвайт-ссылки.
# Для группы/супергруппы это отрицательное число, например: -1001234567890
# Получить можно, добавив @userinfobot в чат и написав /start
CHAT_ID: int | str = os.getenv("CHAT_ID", "YOUR_CHAT_ID_HERE")
