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

    # Генеруємо ключ спеціально для ручної видачі
    real_key = generate_unique_key()
    
    # Зберігаємо його одразу з позначкою is_used = 0, АЛЕ робимо так, 
    # щоб перевірка ключа через сайд-апі /verify_key не блокувала його повторне використання, 
    # або просто видаємо звичайний ключ, якийр людина активує один раз.
    save_key(real_key, target_user_id, tier)

    await message.answer(f"✅ Успішно надано доступ до версії <b>{tier.upper()}</b> для користувача <code>{target_user_id}</code>!\n🔑 Згенерований ключ: <code>{real_key}</code>", parse_mode="HTML")
    
    file_id = get_file_id(tier)
    if file_id:
        try:
            await message.bot.send_message(
                target_user_id, 
                f"🎁 Адміністратор надав вам безкоштовний доступ до версії <b>{tier.upper()}</b>!\n\n"
                f"🔑 <b>Ваш унікальний ключ активації (одноразовий):</b>\n<code>{real_key}</code>\n\n"
                f"Ось ваш файл оновлення:",
                parse_mode="HTML"
            )
            await message.bot.send_document(target_user_id, document=file_id)
        except Exception as e:
            await message.answer(f"⚠️ Доступ у базі збережено, але не вдалося надіслати повідомлення в ЛС користувачу: {e}")
