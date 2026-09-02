import asyncio
import logging
import os
import random
import sqlite3
import string
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
ADMIN_ID = 5565654648
TG_CHANNEL_URL = "https://t.me/mynotesoffc"

dp = Dispatcher()

DB_DIR = "/data" if os.path.exists("/data") else "."
DB_PATH = os.path.join(DB_DIR, "bot_database.db")


class AdminUpload(StatesGroup):
    waiting_for_file = State()


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            user_id INTEGER,
            tier TEXT,
            is_used INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            tier TEXT PRIMARY KEY,
            file_id TEXT
        )
    """)
    conn.commit()
    conn.close()


def generate_unique_key():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    while True:
        chars = string.ascii_uppercase + string.digits
        parts = ["".join(random.choices(chars, k=4)) for _ in range(4)]
        key = "-".join(parts)
        cursor.execute("SELECT key FROM licenses WHERE key = ?", (key,))
        if not cursor.fetchone():
            conn.close()
            return key


def save_key(key: str, user_id: int, tier: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO licenses (key, user_id, tier, is_used) VALUES (?, ?, ?, 0)",
        (key, user_id, tier),
    )
    conn.commit()
    conn.close()


def verify_and_activate_key(key: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key FROM licenses WHERE key = ? AND is_used = 0", (key,)
    )
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE licenses SET is_used = 1 WHERE key = ?", (key,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def get_file_id(tier: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM files WHERE tier = ?", (tier,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None


def set_file_id(tier: str, file_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO files (tier, file_id) VALUES (?, ?)",
        (tier, file_id),
    )
    conn.commit()
    conn.close()


async def verify_key_endpoint(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"valid": False, "error": "Invalid JSON"}, status=400)

    key = data.get("key", "").strip().upper()
    if not key:
        return web.json_response({"valid": False, "error": "No key provided"}, status=400)

    is_valid = verify_and_activate_key(key)
    return web.json_response({"valid": is_valid})


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Free Version", callback_data="get_free")],
            [InlineKeyboardButton(text="⭐ Plus Version (Test Free)", callback_data="get_plus")],
            [InlineKeyboardButton(text="💎 Pro Version (Test Free)", callback_data="get_pro")],
            [InlineKeyboardButton(text="📢 Telegram Channel", url=TG_CHANNEL_URL)],
        ]
    )
    await message.answer(
        "Вітаю! Оберіть версію додатка для тесту:",
        reply_markup=keyboard,
    )


@dp.message(Command("setfile"))
async def cmd_setfile(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer(f"❌ У вас немає прав адміністратора. Ваш ID: {message.from_user.id}")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Free", callback_data="set_free")],
            [InlineKeyboardButton(text="Plus", callback_data="set_plus")],
            [InlineKeyboardButton(text="Pro", callback_data="set_pro")],
        ]
    )
    await message.answer("Оберіть версію, для якої хочете завантажити файл:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("set_"))
async def process_set_tier(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Помилка доступу", show_alert=True)
        return

    tier = callback.data.split("_")[1]
    await state.update_data(tier=tier)
    await state.set_state(AdminUpload.waiting_for_file)
    await callback.message.answer(
        f"📤 Тепер надішліть файл (.exe або архів) у чат для версії <b>{tier}</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(AdminUpload.waiting_for_file)
async def save_new_file(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.document:
        await message.answer("Будь ласка, надішліть файл як ДОКУМЕНТ (з файловою іконкою).")
        return

    data = await state.get_data()
    tier = data.get("tier")
    file_id = message.document.file_id
    set_file_id(tier, file_id)
    await state.clear()
    await message.answer(f"✅ Файл для версії <b>{tier}</b> успішно збережено в базу!", parse_mode="HTML")


@dp.callback_query(F.data == "get_free")
async def send_free(callback: types.CallbackQuery):
    file_id = get_file_id("free")
    if not file_id:
        await callback.answer("Адмін ще не завантажив Free версію!", show_alert=True)
        return
    await callback.message.answer_document(
        document=file_id, caption="📥 Тримайте безкоштовну версію MyNotes!"
    )
    await callback.answer()


@dp.callback_query(F.data.in_({"get_plus", "get_pro"}))
async def process_test_get(callback: types.CallbackQuery):
    tier = "plus" if callback.data == "get_plus" else "pro"
    file_id = get_file_id(tier)

    if not file_id:
        await callback.answer(f"Адмін ще не завантажив файл для версії {tier}!", show_alert=True)
        return

    license_key = generate_unique_key()
    save_key(license_key, callback.from_user.id, tier)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Telegram Channel", url=TG_CHANNEL_URL)]]
    )

    await callback.message.answer(
        f"🎉 Дякуємо! Ось ваша тестова версія {tier.upper()}:\n\n"
        f"🔑 <b>Ваш унікальний одноразовий ключ активації:</b>\n"
        f"<code>{license_key}</code>\n\n"
        f"Скопіюйте його та введіть у додатку при першому запуску (натиснувши Home у грі).",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.message.answer_document(document=file_id)
    await callback.answer()


async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)

    if not TOKEN:
        logging.error("CRITICAL: BOT_TOKEN is not set in environment variables!")
        return

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Найголовніше: повністю видаляємо вебхуки і скидаємо все перед запуском
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    app = web.Application()
    app.router.add_post("/api/verify_key", verify_key_endpoint)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"API server running on port {port}")

    # Запускаємо полінг із примусовим очищенням старих апдейтів
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
