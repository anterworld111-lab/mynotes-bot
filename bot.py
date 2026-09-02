import asyncio
import logging
import random
import sqlite3
import string
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "8854659653:AAFLB5xchIhQtwzlZK3snDKaFJSKx37z_MU"  # <--- Put your bot token here
ADMIN_ID = 5565654648  
  # Твій Telegram ID, щоб бот знав, що ти адмін

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# Стани для завантаження файлів адміном
class AdminUpload(StatesGroup):
  waiting_for_file = State()


def init_db():
  conn = sqlite3.connect("bot_database.db")
  cursor = conn.cursor()
  # Таблиця для ліцензійних ключів
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            user_id INTEGER,
            tier TEXT,
            is_used INTEGER DEFAULT 0
        )
    """)
  # Таблиця для актуальних file_id
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


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="📥 Free Version", callback_data="get_free"
              )
          ],
          [InlineKeyboardButton(text="⭐ Plus Version", callback_data="buy_plus")],
          [InlineKeyboardButton(text="💎 Pro Version", callback_data="buy_pro")],
      ]
  )
  await message.answer(
      "Вітаю! Обирай потрібну версію софту MyNotes:", reply_markup=keyboard
  )


# --- Адмін-частина для оновлення файлів ---
@dp.message(Command("setfile"), F.from_user.id == ADMIN_ID)
async def cmd_setfile(message: types.Message, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="Free", callback_data="set_free")],
          [InlineKeyboardButton(text="Plus", callback_data="set_plus")],
          [InlineKeyboardButton(text="Pro", callback_data="set_pro")],
      ]
  )
  await message.answer(
      "Обери версію, для якої хочеш оновити файл:", reply_markup=keyboard
  )


@dp.callback_query(F.data.startswith("set_"), F.from_user.id == ADMIN_ID)
async def process_set_tier(callback: types.CallbackQuery, state: FSMContext):
  tier = callback.data.split("_")[1]
  await state.update_data(tier=tier)
  await callback.message.answer(
      f"Тепер надішли новий файл (`.exe` або архів) для версії **{tier}**:"
  )
  await state.set_state(AdminUpload.waiting_for_file)
  await callback.answer()


@dp.message(AdminUpload.waiting_for_file, F.from_user.id == ADMIN_ID)
async def save_new_file(message: types.Message, state: FSMContext):
  if not message.document:
    await message.answer("Будь ласка, надішли саме файл (як документ).")
    return

  data = await state.get_data()
  tier = data.get("tier")
  file_id = message.document.file_id

  set_file_id(tier, file_id)
  await state.clear()
  await message.answer(
      f"✅ Файл для версії **{tier}** успішно оновлено в базі!"
  )


# --- Користувацька частина ---
@dp.callback_query(F.data == "get_free")
async def send_free(callback: types.CallbackQuery):
  file_id = get_file_id("free")
  if not file_id:
    await callback.answer(
        "Безкоштовна версія ще не завантажена адміністратором.", show_alert=True
    )
    return
  await callback.message.answer_document(
      document=file_id, caption="Ось твоя безкоштовна версія MyNotes!"
  )
  await callback.answer()


@dp.callback_query(F.data.in_({"buy_plus", "buy_pro"}))
async def process_purchase(callback: types.CallbackQuery):
  tier = "plus" if callback.data == "buy_plus" else "pro"
  file_id = get_file_id(tier)

  if not file_id:
    await callback.answer(
        "Ця версія ще не завантажена адміністратором.", show_alert=True
    )
    return

  license_key = generate_unique_key()
  save_key(license_key, callback.from_user.id, tier)

  await callback.message.answer(
      f"✅ Оплата успішна! Ось твоя версія софту:\n\n"
      f"🔑 Твій ліцензійний ключ (12 символів, одноразовий):\n"
      f"<code>{license_key}</code>\n\n"
      f"Збережи його, при першому запуску програми його потрібно буде ввести.",
      parse_mode="HTML",
  )
  await callback.message.answer_document(document=file_id)
  await callback.answer()


async def main():
  init_db()
  logging.basicConfig(level=logging.INFO)
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
