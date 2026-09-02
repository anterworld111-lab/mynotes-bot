import asyncio
import logging
import os
import random
import sqlite3
import string
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Зчитуємо токен із змінних Railway (перевіряє і BOT_TOKEN, і TOKEN)
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
ADMIN_ID = 5565654648
TG_CHANNEL_URL = "https://t.me/mynotesoffc"

dp = Dispatcher()


class AdminUpload(StatesGroup):
    waiting_for_file = State()


def init_db():
    conn = sqlite3.connect("bot_database.db")
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
    conn = sqlite3.connect("bot_database.db")
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
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO licenses (key, user_id, tier, is_used) VALUES (?, ?, ?, 0)",
        (key, user_id, tier),
    )
    conn.commit()
    conn.close()


def verify_and_activate_key(key: str) -> bool:
    conn = sqlite3.connect("bot_database.db")
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
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM files WHERE tier = ?", (tier,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None


def set_file_id(tier: str, file_id: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO files (tier, file_id) VALUES (?, ?)",
        (tier, file_id),
    )
    conn.commit()
    conn.close()


# --- HTTP API ДЛЯ GODOT ---
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


# --- ОБРОБНИКИ ТЕЛЕГРАМ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Free Version", callback_data="get_free")],
            [InlineKeyboardButton(text="⭐ Plus Version", callback_data="buy_plus")],
            [InlineKeyboardButton(text="💎 Pro Version", callback_data="buy_pro")],
            [InlineKeyboardButton(text="📢 Telegram Channel", url=TG_CHANNEL_URL)],
        ]
    )
    await message.answer(
        "Welcome! Choose the required version of MyNotes / Ласкаво просимо! Оберіть версію MyNotes:",
        reply_markup=keyboard,
    )


@dp.message(Command("setfile"), F.from_user.id == ADMIN_ID)
async def cmd_setfile(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Free", callback_data="set_free")],
            [InlineKeyboardButton(text="Plus", callback_data="set_plus")],
            [InlineKeyboardButton(text="Pro", callback_data="set_pro")],
        ]
    )
    await message.answer("Choose the version to update the file for:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("set_"), F.from_user.id == ADMIN_ID)
async def process_set_tier(callback: types.CallbackQuery, state: FSMContext):
    tier = callback.data.split("_")[1]
    await state.update_data(tier=tier)
    await state.set_state(AdminUpload.waiting_for_file)
    await callback.message.answer(
        f"Now send the new file (.exe or archive) for the <b>{tier}</b> version:",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(AdminUpload.waiting_for_file, F.from_user.id == ADMIN_ID)
async def save_new_file(message: types.Message, state: FSMContext):
    if not message.document:
        await message.answer("Please send a file (as a document).")
        return
    data = await state.get_data()
    tier = data.get("tier")
    file_id = message.document.file_id
    set_file_id(tier, file_id)
    await state.clear()
    await message.answer(f"✅ File for <b>{tier}</b> successfully updated in DB!", parse_mode="HTML")


@dp.callback_query(F.data == "get_free")
async def send_free(callback: types.CallbackQuery):
    file_id = get_file_id("free")
    if not file_id:
        await callback.answer("Free version is not uploaded by admin yet.", show_alert=True)
        return
    await callback.message.answer_document(
        document=file_id, caption="Here is your free version of MyNotes!"
    )
    await callback.answer()


@dp.callback_query(F.data.in_({"buy_plus", "buy_pro"}))
async def process_purchase(callback: types.CallbackQuery):
    tier = "plus" if callback.data == "buy_plus" else "pro"
    file_id = get_file_id(tier)

    if not file_id:
        await callback.answer("This version is not uploaded by admin yet.", show_alert=True)
        return

    license_key = generate_unique_key()
    save_key(license_key, callback.from_user.id, tier)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Telegram Channel", url=TG_CHANNEL_URL)]]
    )

    await callback.message.answer(
        f"✅ Payment successful! Here is your software version:\n\n"
        f"🔑 Your license key (one-time use):\n"
        f"<code>{license_key}</code>\n\n"
        f"Save it, you will need to enter it on the first launch.",
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

    bot = Bot(token=TOKEN)

    # Веб-сервер API для перевірки ключів з Godot
    app = web.Application()
    app.router.add_post("/api/verify_key", verify_key_endpoint)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"API server running on port {port}")

    # Запуск бота в Telegram
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
