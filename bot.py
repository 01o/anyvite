import asyncio
import random
import logging
import time
from collections import deque
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, CHAT_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ─── Очередь и rate limit ─────────────────────────────────────────────────────

RATE_LIMIT_SECONDS = 300  # 5 минут между выдачами ссылок

invite_queue: deque = deque()   # (user_id, message_id, chat_id)
last_issued_at: float = 0.0     # timestamp последней выданной ссылки
queued_users: dict = {}         # user_id → True

async def queue_worker():
    """Фоновая задача: раз в секунду проверяет очередь и выдаёт ссылку если прошло 5 минут."""
    global last_issued_at
    while True:
        await asyncio.sleep(1)
        if not invite_queue:
            continue

        now = time.time()
        elapsed = now - last_issued_at

        if elapsed < RATE_LIMIT_SECONDS:
            # Обновляем таймер у всех в очереди раз в 10 секунд (чтобы не спамить Telegram API)
            if int(elapsed) % 10 != 0:
                continue
            wait_base = RATE_LIMIT_SECONDS - elapsed
            for pos, (uid, mid, cid) in enumerate(invite_queue):
                total_wait = int(wait_base + pos * RATE_LIMIT_SECONDS)
                mins, secs = divmod(total_wait, 60)
                try:
                    await bot.edit_message_text(
                        chat_id=cid,
                        message_id=mid,
                        text=(
                            f"⏳ Ты в очереди на получение ссылки.\n\n"
                            f"📍 Позиция: <b>{pos + 1}</b>\n"
                            f"🕐 Примерное ожидание: <b>{mins} мин {secs} сек</b>"
                        ),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            continue

        # Выдаём ссылку первому в очереди
        user_id, msg_id, chat_id = invite_queue.popleft()
        queued_users.pop(user_id, None)
        last_issued_at = time.time()

        try:
            link = await bot.create_chat_invite_link(
                chat_id=CHAT_ID,
                member_limit=1,
                name=f"user_{user_id}",
            )
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=(
                    f"🎉 Твоя одноразовая ссылка для входа:\n\n"
                    f"<b>{link.invite_link}</b>\n\n"
                    "⚠️ Ссылка действует только для <b>одного</b> входа.\n"
                    "Чтобы получить новую — отправь /start."
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to create invite link for {user_id}: {e}")
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text="❌ Не удалось создать ссылку. Попробуй снова: /start",
                )
            except Exception:
                pass

# ─── Капча ────────────────────────────────────────────────────────────────────

class CaptchaState(StatesGroup):
    waiting_for_captcha = State()

def generate_math_captcha() -> tuple[str, int]:
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(['+', '-', '*'])
    if op == '+':
        answer = a + b
    elif op == '-':
        answer = a - b
    else:
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        answer = a * b
    return f"{a} {op} {b}", answer

def build_captcha_keyboard(correct: int) -> InlineKeyboardMarkup:
    options = {correct}
    while len(options) < 4:
        candidate = correct + random.randint(-10, 10)
        if candidate != correct:
            options.add(candidate)
    buttons = [
        InlineKeyboardButton(text=str(v), callback_data=f"captcha:{v}:{correct}")
        for v in sorted(options, key=lambda x: random.random())
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

# ─── Обработчики ──────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    if message.from_user.id in queued_users:
        pos = next(
            (i for i, (uid, _, _) in enumerate(invite_queue) if uid == message.from_user.id), 0
        )
        now = time.time()
        wait_base = max(RATE_LIMIT_SECONDS - (now - last_issued_at), 0)
        total_wait = int(wait_base + pos * RATE_LIMIT_SECONDS)
        mins, secs = divmod(total_wait, 60)
        await message.answer(
            f"⏳ Ты уже в очереди!\n\n"
            f"📍 Позиция: <b>{pos + 1}</b>\n"
            f"🕐 Примерное ожидание: <b>{mins} мин {secs} сек</b>",
            parse_mode="HTML",
        )
        return

    question, answer = generate_math_captcha()
    await state.set_state(CaptchaState.waiting_for_captcha)
    await state.update_data(correct_answer=answer, attempts=0)

    await message.answer(
        "👋 Привет! Я выдаю одноразовые ссылки для входа в чат.\n\n"
        "🔐 <b>Сначала пройди капчу:</b>\n\n"
        f"Сколько будет: <code>{question} = ?</code>",
        parse_mode="HTML",
        reply_markup=build_captcha_keyboard(answer),
    )

@dp.callback_query(F.data.startswith("captcha:"), CaptchaState.waiting_for_captcha)
async def process_captcha(callback: CallbackQuery, state: FSMContext):
    global last_issued_at
    _, chosen_str, correct_str = callback.data.split(":")
    chosen = int(chosen_str)
    correct = int(correct_str)
    data = await state.get_data()
    attempts = data.get("attempts", 0) + 1

    if chosen == correct:
        await state.clear()
        user_id = callback.from_user.id
        now = time.time()
        elapsed = now - last_issued_at

        # Выдаём сразу — очередь пуста и кулдаун прошёл
        if not invite_queue and elapsed >= RATE_LIMIT_SECONDS:
            last_issued_at = time.time()
            await callback.message.edit_text("✅ Капча пройдена! Генерирую ссылку...")
            try:
                link = await bot.create_chat_invite_link(
                    chat_id=CHAT_ID,
                    member_limit=1,
                    name=f"user_{user_id}",
                )
                await callback.message.edit_text(
                    f"🎉 Твоя одноразовая ссылка для входа:\n\n"
                    f"<b>{link.invite_link}</b>\n\n"
                    "⚠️ Ссылка действует только для <b>одного</b> входа.\n"
                    "Чтобы получить новую — отправь /start.",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to create invite link: {e}")
                await callback.message.edit_text(
                    "❌ Не удалось создать ссылку. Убедись, что бот является администратором чата "
                    "с правом приглашать участников.\n\nПопробуй снова: /start"
                )
        else:
            # Ставим в очередь
            pos = len(invite_queue)
            wait_base = max(RATE_LIMIT_SECONDS - elapsed, 0)
            total_wait = int(wait_base + pos * RATE_LIMIT_SECONDS)
            mins, secs = divmod(total_wait, 60)

            sent = await callback.message.edit_text(
                f"✅ Капча пройдена! Ты добавлен в очередь.\n\n"
                f"📍 Позиция: <b>{pos + 1}</b>\n"
                f"🕐 Примерное ожидание: <b>{mins} мин {secs} сек</b>",
                parse_mode="HTML",
            )
            invite_queue.append((user_id, sent.message_id, callback.message.chat.id))
            queued_users[user_id] = True

    else:
        if attempts >= 3:
            await state.clear()
            await callback.message.edit_text(
                "❌ Слишком много неверных попыток. Попробуй снова: /start"
            )
        else:
            await state.update_data(attempts=attempts)
            question, answer = generate_math_captcha()
            await state.update_data(correct_answer=answer)
            await callback.message.edit_text(
                f"❌ Неверно! Попытка {attempts}/3.\n\n"
                f"Попробуй ещё раз: <code>{question} = ?</code>",
                parse_mode="HTML",
                reply_markup=build_captcha_keyboard(answer),
            )

    await callback.answer()

# ─── Запуск ───────────────────────────────────────────────────────────────────

async def main():
    asyncio.create_task(queue_worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
