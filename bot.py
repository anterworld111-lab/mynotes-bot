import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Твій токен від @BotFather
TOKEN = "8854659653:AAFLB5xchIhQtwzlZK3snDKaFJSKx37z_MU"

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Download Basic", callback_data="download_basic"),
            InlineKeyboardButton(text="⭐ Get Plus / Pro", callback_data="upgrade_pro")
        ],
        [
            InlineKeyboardButton(text="🌐 Official Channel", url="https://t.me/mynotesoffc")
        ]
    ])
    return keyboard

async def cmd_start(message: Message):
    welcome_text = (
        "👋 Welcome to **MyNotes Bot**!\n\n"
        "Here you can choose your software version, download updates, "
        "and unlock Plus or Pro tiers.\n\n"
        "Select an option below:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

async def handle_callbacks(callback):
    data = callback.data
    if data == "download_basic":
        await callback.message.answer("📥 **MyNotes Basic** is completely free! Check our official channel for direct downloads.")
    elif data == "upgrade_pro":
        await callback.message.answer("⭐ To unlock **Plus** or **Pro** editions, contact the administration or check pinned posts on our channel.")
    
    await callback.answer()

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    
    dp.message.register(cmd_start, CommandStart())
    dp.callback_query.register(handle_callbacks)
    
    print("Бот успішно запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())