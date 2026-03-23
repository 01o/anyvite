import asyncio
import random
import logging
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

# ─── Капча ────────────────────────────────────────────────────────────────────

class CaptchaState(StatesGroup):
    waiting_for_captcha = State()

def generate_math_captcha() -> tuple[str, int]:
    """Генерирует простой математический пример. Возвращает (вопрос, ответ)."""
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
    question = f"{a} {op} {b}"
    return question, answer

def build_captcha_keyboard(correct: int) -> InlineKeyboardMarkup:
    """Строит клавиатуру с 4 вариантами ответа (один правильный)."""
    options = {correct}
    while len(options) < 4:
        delta = random.randint(-10, 10)
        candidate = correct + delta
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
    question, answer = generate_math_captcha()
    await state.set_state(CaptchaState.waiting_for_captcha)
    await state.update_data(correct_answer=answer, attempts=0)

    keyboard = build_captcha_keyboard(answer)
    await message.answer(
        "👋 Привет! Я выдаю одноразовые ссылки для входа в чат.\n\n"
        "🔐 <b>Сначала пройди капчу:</b>\n\n"
        f"Сколько будет: <code>{question} = ?</code>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )

@dp.callback_query(F.data.startswith("captcha:"), CaptchaState.waiting_for_captcha)
async def process_captcha(callback: CallbackQuery, state: FSMContext):
    _, chosen_str, correct_str = callback.data.split(":")
    chosen = int(chosen_str)
    correct = int(correct_str)
    data = await state.get_data()
    attempts = data.get("attempts", 0) + 1

    if chosen == correct:
        await state.clear()
        await callback.message.edit_text("✅ Капча пройдена! Генерирую ссылку...")

        try:
            link = await bot.create_chat_invite_link(
                chat_id=CHAT_ID,
                member_limit=1,        # одноразовая
                name=f"user_{callback.from_user.id}",
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
        if attempts >= 3:
            await state.clear()
            await callback.message.edit_text(
                "❌ Слишком много неверных попыток. Попробуй снова: /start"
            )
        else:
            await state.update_data(attempts=attempts)
            # Генерируем новый вопрос
            question, answer = generate_math_captcha()
            await state.update_data(correct_answer=answer)
            keyboard = build_captcha_keyboard(answer)
            await callback.message.edit_text(
                f"❌ Неверно! Попытка {attempts}/3.\n\n"
                f"Попробуй ещё раз: <code>{question} = ?</code>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

    await callback.answer()

# ─── Запуск ───────────────────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
