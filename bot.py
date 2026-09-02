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
ADMIN_ID = 5565654648  


bot = Bot(token=TOKEN)
dp = Dispatcher()

# Додали сюди ще й 'free' для безкоштовної версії
version_files = {"free": None, "plus": None, "pro": None}
buyers = {"free": set(), "plus": set(), "pro": set()}

TEST_MODE = False  # False = бойовий режим (Telegram Stars)


def get_main_keyboard():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="📥 Download Free Version", callback_data="get_free"
              )
          ],
          [
              InlineKeyboardButton(
                  text="⭐ Buy MyNotes Plus (200 Stars)",
                  callback_data="buy_plus",
              )
          ],
          [
              InlineKeyboardButton(
                  text="🚀 Buy MyNotes Pro (400 Stars)",
                  callback_data="buy_pro",
              )
          ],
          [
              InlineKeyboardButton(
                  text="📢 Official Channel", url="https://t.me/mynotesoffc"
              )
          ],
      ]
  )


@dp.message(CommandStart())
async def cmd_start(message: Message):
  await message.answer(
      "Welcome to MyNotes! Choose what you want to get:",
      reply_markup=get_main_keyboard(),
  )


# --- GET FREE VERSION ---
@dp.callback_query(F.data == "get_free")
async def process_get_free(callback: CallbackQuery):
  user_id = callback.from_user.id
  buyers["free"].add(user_id)

  if version_files["free"]:
    await callback.message.answer_document(
        document=version_files["free"],
        caption="🎁 Here is your Free version of MyNotes!",
    )
  else:
    await callback.answer(
        "❌ Free version is currently unavailable! Admin hasn't uploaded it"
        " yet.",
        show_alert=True,
    )
  await callback.answer()


# --- BUY PLUS VERSION ---
@dp.callback_query(F.data == "buy_plus")
async def process_buy_plus(callback: CallbackQuery):
  user_id = callback.from_user.id
  if TEST_MODE:
    buyers["plus"].add(user_id)
    if version_files["plus"]:
      await callback.message.answer_document(
          document=version_files["plus"],
          caption="🎁 [TEST] Here is your MyNotes Plus version!",
      )
    else:
      await callback.message.answer(
          "⚠️ Test successful, but the admin hasn't uploaded the Plus file yet!"
      )
    await callback.answer()
  else:
    if not version_files["plus"]:
      await callback.answer(
          "❌ MyNotes Plus is currently unavailable! Try again later.",
          show_alert=True,
      )
      return

    prices = [LabeledPrice(label="MyNotes Plus", amount=200)]
    await callback.message.answer_invoice(
        title="MyNotes Plus",
        description="Access to MyNotes Plus version (200 Stars)",
        prices=prices,
        provider_token="",
        payload="payload_plus",
        currency="XTR",
    )
    await callback.answer()


# --- BUY PRO VERSION ---
@dp.callback_query(F.data == "buy_pro")
async def process_buy_pro(callback: CallbackQuery):
  user_id = callback.from_user.id
  if TEST_MODE:
    buyers["pro"].add(user_id)
    if version_files["pro"]:
      await callback.message.answer_document(
          document=version_files["pro"],
          caption="🎁 [TEST] Here is your MyNotes Pro version!",
      )
    else:
      await callback.message.answer(
          "⚠️ Test successful, but the admin hasn't uploaded the Pro file yet!"
      )
    await callback.answer()
  else:
    if not version_files["pro"]:
      await callback.answer(
          "❌ MyNotes Pro is currently unavailable! Try again later.",
          show_alert=True,
      )
      return

    prices = [LabeledPrice(label="MyNotes Pro", amount=400)]
    await callback.message.answer_invoice(
        title="MyNotes Pro",
        description="Access to MyNotes Pro version (400 Stars)",
        prices=prices,
        provider_token="",
        payload="payload_pro",
        currency="XTR",
    )
    await callback.answer()


# --- STARS PAYMENT CONFIRMATION ---
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query):
  payload = pre_checkout_query.invoice_payload

  if payload == "payload_plus" and not version_files["plus"]:
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=False,
        error_message=(
            "Sorry, the MyNotes Plus file is no longer available. Your stars"
            " will not be charged."
        ),
    )
    return

  if payload == "payload_pro" and not version_files["pro"]:
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=False,
        error_message=(
            "Sorry, the MyNotes Pro file is no longer available. Your stars will"
            " not be charged."
        ),
    )
    return

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
          caption="🎉 Thank you for purchasing MyNotes Plus!",
      )
  elif payload == "payload_pro":
    buyers["pro"].add(user_id)
    if version_files["pro"]:
      await message.answer_document(
          document=version_files["pro"],
          caption="🎉 Thank you for purchasing MyNotes Pro!",
      )


# --- ADMIN PANEL: FILE UPLOAD & BROADCAST ---
pending_admin_files = {}


@dp.message(F.document)
async def admin_upload_file(message: Message):
  if message.from_user.id != ADMIN_ID:
    return

  file_id = message.document.file_id
  pending_admin_files[message.from_user.id] = file_id

  kb = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="📥 Save as FREE Version", callback_data="save_as_free"
              )
          ],
          [
              InlineKeyboardButton(
                  text="📦 Save as PLUS Version", callback_data="save_as_plus"
              )
          ],
          [
              InlineKeyboardButton(
                  text="🚀 Save as PRO Version", callback_data="save_as_pro"
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
      "📂 File received. Choose what version this file is:", reply_markup=kb
  )


@dp.callback_query(
    F.data.in_({"save_as_free", "save_as_plus", "save_as_pro"})
)
async def confirm_version_update(callback: CallbackQuery):
  admin_id = callback.from_user.id
  if admin_id not in pending_admin_files:
    await callback.message.answer("Error: file not found or expired.")
    return

  file_id = pending_admin_files[admin_id]

  if callback.data == "save_as_free":
    version_type = "free"
  elif callback.data == "save_as_plus":
    version_type = "plus"
  else:
    version_type = "pro"

  version_files[version_type] = file_id
  del pending_admin_files[admin_id]

  await callback.message.edit_text(
      f"✅ File successfully saved as {version_type.upper()}"
      + ("!" if version_type == "free" else " and starting broadcast...")
  )
  await callback.answer()

  # Розсилка оновлень тільки для платних версій, якщо це оновлення
  if version_type != "free":
    target_users = buyers[version_type]
    success_count = 0

    for uid in target_users:
      try:
        await bot.send_document(
            chat_id=uid,
            document=file_id,
            caption=(
                f"🔄 An update is available for your MyNotes"
                f" {version_type.upper()} version!"
            ),
        )
        success_count += 1
      except Exception:
        pass

    await bot.send_message(
        chat_id=admin_id,
        text=(
            f"📢 Broadcast completed! Successfully sent to {success_count}"
            " users."
        ),
    )


@dp.callback_query(F.data == "cancel_admin")
async def cancel_admin_action(callback: CallbackQuery):
  if callback.from_user.id in pending_admin_files:
    del pending_admin_files[callback.from_user.id]
  await callback.message.edit_text("❌ Action cancelled.")
  await callback.answer()


async def main():
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
