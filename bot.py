import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
)

TOKEN = "8854659653:AAFLB5xchIhQtwzlZK3snDKaFJSKx37z_MU"  # <--- Put your bot token here
ADMIN_ID = 5565654648  # <--- Put your numeric Telegram Admin ID here

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Databases in memory for testing
version_files = {"plus": None, "pro": None}
buyers = {"plus": set(), "pro": set()}

TEST_MODE = True  # True = Free test mode, False = Real Telegram Stars payments


# Main menu for regular users
def get_main_keyboard():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="⭐ Buy Plus (200 Stars / 150 UAH)",
                  callback_data="buy_plus",
              )
          ],
          [
              InlineKeyboardButton(
                  text="🚀 Buy Pro (500 Stars / 350 UAH)",
                  callback_data="buy_pro",
              )
          ],
      ]
  )


@dp.message(CommandStart())
async def cmd_start(message: Message):
  await message.answer(
      "Welcome! Choose the version you want to get:",
      reply_markup=get_main_keyboard(),
  )


# --- BUY / TEST PLUS VERSION ---
@dp.callback_query(F.data == "buy_plus")
async def process_buy_plus(callback: CallbackQuery):
  user_id = callback.from_user.id
  if TEST_MODE:
    buyers["plus"].add(user_id)
    if version_files["plus"]:
      await callback.message.answer_document(
          document=version_files["plus"],
          caption=(
              "🎁 [TEST MODE] Here is your Plus version! You will receive"
              " automatic updates when a new version is released."
          ),
      )
    else:
      await callback.message.answer(
          "⚠️ Test successful, but the admin hasn't uploaded the Plus file"
          " yet!"
      )
    await callback.answer()
  else:
    prices = [LabeledPrice(label="Plus Version", amount=200)]
    await callback.message.answer_invoice(
        title="Plus Version",
        description="Access to Plus version (200 Stars / 150 UAH)",
        prices=prices,
        provider_token="",
        payload="payload_plus",
        currency="XTR",
    )
    await callback.answer()


# --- BUY / TEST PRO VERSION ---
@dp.callback_query(F.data == "buy_pro")
async def process_buy_pro(callback: CallbackQuery):
  user_id = callback.from_user.id
  if TEST_MODE:
    buyers["pro"].add(user_id)
    if version_files["pro"]:
      await callback.message.answer_document(
          document=version_files["pro"],
          caption=(
              "🎁 [TEST MODE] Here is your Pro version! You will receive"
              " automatic updates when a new version is released."
          ),
      )
    else:
      await callback.message.answer(
          "⚠️ Test successful, but the admin hasn't uploaded the Pro file yet!"
      )
    await callback.answer()
  else:
    prices = [LabeledPrice(label="Pro Version", amount=500)]
    await callback.message.answer_invoice(
        title="Pro Version",
        description="Access to Pro version (500 Stars / 350 UAH)",
        prices=prices,
        provider_token="",
        payload="payload_pro",
        currency="XTR",
    )
    await callback.answer()


# --- STARS PAYMENT CONFIRMATION ---
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query):
  await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
  user_id = message.from_user.id
  payload = message.successful_payment.invoice_payload

  if payload == "payload_plus":
    buyers["plus"].add(user_id)
    if version_files["plus"]:
      await message.answer_document(
          document=version_files["plus"],
          caption="🎉 Thank you for purchasing the Plus version!",
      )
  elif payload == "payload_pro":
    buyers["pro"].add(user_id)
    if version_files["pro"]:
      await message.answer_document(
          document=version_files["pro"],
          caption="🎉 Thank you for purchasing the Pro version!",
      )


# --- ADMIN PANEL: FILE UPLOAD & BROADCAST ---
pending_admin_files = {}


@dp.message(F.document)
async def admin_upload_file(message: Message):
  if message.from_user.id != ADMIN_ID:
    return  # Ignore regular users

  file_id = message.document.file_id
  pending_admin_files[message.from_user.id] = file_id

  kb = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="📦 Update PLUS Version", callback_data="save_as_plus"
              )
          ],
          [
              InlineKeyboardButton(
                  text="🚀 Update PRO Version", callback_data="save_as_pro"
              )
          ],
          [
              InlineKeyboardButton(
                  text="❌ Cancel", callback_data="cancel_admin"
              )
          ],
      ]
  )
  await message.answer(
      "📂 File received. Choose where to apply this file (this will trigger a"
      " broadcast to buyers):",
      reply_markup=kb,
  )


@dp.callback_query(F.data.in_({"save_as_plus", "save_as_pro"}))
async def confirm_version_update(callback: CallbackQuery):
  admin_id = callback.from_user.id
  if admin_id not in pending_admin_files:
    await callback.message.answer("Error: file not found or expired.")
    return

  file_id = pending_admin_files[admin_id]
  version_type = "plus" if callback.data == "save_as_plus" else "pro"

  version_files[version_type] = file_id
  del pending_admin_files[admin_id]

  await callback.message.edit_text(
      f"✅ File updated for {version_type.upper()}! Starting broadcast..."
  )
  await callback.answer()

  target_users = buyers[version_type]
  success_count = 0

  for uid in target_users:
    try:
      await bot.send_document(
          chat_id=uid,
          document=file_id,
          caption=(
              f"🔄 An update is available for your {version_type.upper()}"
              " version! Here is the new file:"
          ),
      )
      success_count += 1
    except Exception:
      pass

  await bot.send_message(
      chat_id=admin_id,
      text=(
          f"📢 Broadcast completed! Successfully sent to {success_count} users."
      ),
  )


@dp.callback_query(F.data == "cancel_admin")
async def cancel_admin_action(callback: CallbackQuery):
  if callback.from_user.id in pending_admin_files:
    del pending_admin_files[callback.from_user.id]
  await callback.message.edit_text("❌ Action cancelled.")
  await callback.answer()


# Bot startup
async def main():
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
