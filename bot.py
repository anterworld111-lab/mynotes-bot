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


class AdminKeyGen(StatesGroup):
    waiting_for_tier = State()


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


def user_has_tier(user_id: int, tier: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if tier == "plus":
        cursor.execute("SELECT 1 FROM licenses WHERE user_id = ? AND tier IN ('plus', 'pro')", (user_id,))
    elif tier == "pro":
        cursor.execute("SELECT 1 FROM licenses WHERE user_id = ? AND tier = 'pro'", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None


def get_users_by_tier(tier: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if tier == "plus":
        cursor.execute("SELECT DISTINCT user_id FROM licenses WHERE tier IN ('plus', 'pro') AND user_id != ?", (ADMIN_ID,))
    else:
        cursor.execute("SELECT DISTINCT user_id FROM licenses WHERE tier = 'pro' AND user_id != ?", (ADMIN_ID,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


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
            [InlineKeyboardButton(text="⭐ Plus Version (100 Stars)", callback_data="buy_plus")],
            [InlineKeyboardButton(text="💎 Pro Version (250 Stars)", callback_data="buy_pro")],
            [InlineKeyboardButton(text="📢 Telegram Channel", url=TG_CHANNEL_URL)],
        ]
    )
    await message.answer(
        "Welcome! Choose the app version:",
        reply_markup=keyboard,
    )


@dp.message(Command("setfile"))
async def cmd_setfile(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer(f"❌ У вас немає прав адміністратора. Ваш ID: {message.from_user.id}")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Free", callback_data="set_free"), InlineKeyboardButton(text="Plus", callback_data="set_plus"), InlineKeyboardButton(text="Pro", callback_data="set_pro")],
            [InlineKeyboardButton(text="🔑 Згенерувати ключ", callback_data="admin_gen_key")]
        ]
    )
    await message.answer("🛠️ [Адмін-панель] Оберіть дію або версію для завантаження файлу:", reply_markup=keyboard)


@dp.message(Command("give_access"))
async def cmd_give_access(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас немає прав адміністратора.")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Неправильний формат!\nВикористання: <code>/give_access [user_id] [plus/pro]</code>", parse_mode="HTML")
        return

    try:
        target_user_id = int(args[1])
        tier = args[2].lower()
    except ValueError:
        await message.answer("❌ ID користувача має бути числом!")
        return

    if tier not in ["plus", "pro"]:
        await message.answer("❌ Тір може бути тільки <code>plus</code> або <code>pro</code>!", parse_mode="HTML")
        return

    real_key = generate_unique_key()
    save_key(real_key, target_user_id, tier)

    await message.answer(f"✅ Успішно надано доступ до версії <b>{tier.upper()}</b> для користувача <code>{target_user_id}</code>!\n🔑 Згенерований ключ: <code>{real_key}</code>", parse_mode="HTML")
    
    file_id = get_file_id(tier)
    if file_id:
        try:
            await message.bot.send_message(
                target_user_id, 
                f"🎁 Адміністратор надав вам безкоштовний доступ до версії <b>{tier.upper()}</b>!\n\n"
                f"🔑 <b>Ваш унікальний ключ активації:</b>\n<code>{real_key}</code>\n\n"
                f"Ось ваш файл оновлення:",
                parse_mode="HTML"
            )
            await message.bot.send_document(target_user_id, document=file_id)
        except Exception as e:
            await message.answer(f"⚠️ Доступ у базі збережено, але не вдалося надіслати повідомлення в ЛС користувачу (можливо, він не запустив бота): {e}")
    else:
        await message.answer("⚠️ Доступ у базі збережено, але файл для цього тіру ще не завантажений через /setfile. Користувач отримає його під час наступного оновлення.")


@dp.callback_query(F.data == "admin_gen_key")
async def admin_gen_key_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Помилка доступу", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Plus", callback_data="gen_plus"), InlineKeyboardButton(text="Pro", callback_data="gen_pro")]
        ]
    )
    await callback.message.answer("🔑 Оберіть тір для генерації унікального ключа:", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.in_({"gen_plus", "gen_pro"}))
async def admin_create_key_finish(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Помилка доступу", show_alert=True)
        return

    tier = "plus" if callback.data == "gen_plus" else "pro"
    new_key = generate_unique_key()
    save_key(new_key, ADMIN_ID, tier)

    await callback.message.answer(
        f"✅ Успішно створено новий ключ для версії <b>{tier.upper()}</b>:\n\n"
        f"<code>{new_key}</code>\n\n"
        f"Можете передати його будь-кому.",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("set_"))
async def process_set_tier(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Помилка доступу", show_alert=True)
        return

    tier = callback.data.split("_")[1]
    await state.update_data(tier=tier)
    await state.set_state(AdminUpload.waiting_for_file)
    await callback.message.answer(
        f"📤 [Адмін-панель] Надішліть новий файл (.exe або архів) у чат для версії <b>{tier}</b> (буде розіслано покупцям):",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(AdminUpload.waiting_for_file)
async def save_new_file(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.document:
        await message.answer("🛠️ [Адмін-панель] Будь ласка, надішліть файл як ДОКУМЕНТ.")
        return

    data = await state.get_data()
    tier = data.get("tier")
    file_id = message.document.file_id
    set_file_id(tier, file_id)
    await state.clear()
    
    await message.answer(f"✅ [Адмін-панель] Файл для версії <b>{tier}</b> збережено! Починаю розсилку покупцям...", parse_mode="HTML")

    if tier in ["plus", "pro"]:
        buyers = get_users_by_tier(tier)
        success_count = 0
        for user_id in buyers:
            try:
                await message.bot.send_message(
                    user_id, 
                    f"🔥 Вийшло оновлення для вашої версії <b>{tier.upper()}</b>! Ось новий файл:"
                )
                await message.bot.send_document(user_id, document=file_id)
                success_count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logging.error(f"Не вдалося надіслати оновлення користувачу {user_id}: {e}")
        
        await message.answer(f"📢 Розсилку завершено! Оновлення отримали <b>{success_count}</b> покупців.", parse_mode="HTML")
    else:
        await message.answer("ℹ️ Для Free версії розсилка не потрібна (доступна через кнопку в меню).")


@dp.callback_query(F.data == "get_free")
async def send_free(callback: types.CallbackQuery):
    file_id = get_file_id("free")
    if not file_id:
        await callback.answer("Free version is not uploaded by admin yet!", show_alert=True)
        return
    await callback.message.answer_document(
        document=file_id, caption="📥 Here is your Free version of MyNotes!"
    )
    await callback.answer()


@dp.callback_query(F.data.in_({"buy_plus", "buy_pro"}))
async def process_buy(callback: types.CallbackQuery):
    tier = "plus" if callback.data == "buy_plus" else "pro"
    user_id = callback.from_user.id

    if tier == "plus":
        if user_has_tier(user_id, "plus"):
            await callback.answer("⚠️ У вас вже є підписка Plus або Pro версії!", show_alert=True)
            return
    elif tier == "pro":
        if user_has_tier(user_id, "pro"):
            await callback.answer("⚠️ У вас вже активована Pro версія!", show_alert=True)
            return

    price = 100 if tier == "plus" else 250
    title = "MyNotes Plus Version" if tier == "plus" else "MyNotes Pro Version"
    description = f"License key for MyNotes {tier.upper()} (Lifetime access)"

    prices = [types.LabeledPrice(label=title, amount=price)]
    
    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=f"license_{tier}",
        currency="XTR",
        prices=prices
    )
    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    tier = payload.split("_")[1] if "_" in payload else "plus"
    file_id = get_file_id(tier)

    if not file_id:
        await message.answer("Payment received, but admin has not uploaded the file for this version yet! Contact support.")
        return

    license_key = generate_unique_key()
    save_key(license_key, message.from_user.id, tier)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Telegram Channel", url=TG_CHANNEL_URL)]]
    )

    await message.answer(
        f"🎉 Thank you for your purchase! Here is your {tier.upper()} version:\n\n"
        f"🔑 <b>Your unique activation key:</b>\n"
        f"<code>{license_key}</code>\n\n"
        f"Copy it and enter it inside the app on first launch (press Home in-game).",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await message.answer_document(document=file_id)


async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)

    if not TOKEN:
        logging.error("CRITICAL: BOT_TOKEN is not set in environment variables!")
        return

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

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

    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
