# bot/admin.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
import config
import database as db

logger = logging.getLogger(__name__)

# ========== حالات المحادثة الإدارية ==========
(
    ADMIN_MAIN,
    ADMIN_AWAITING_ADD_POINTS,
    ADMIN_AWAITING_REMOVE_POINTS,
    ADMIN_AWAITING_GIFT,
    ADMIN_AWAITING_BAN,
    ADMIN_AWAITING_UNBAN,
) = range(6)

def is_admin(user_id):
    return user_id == config.ADMIN_ID

def get_admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 إدارة النقاط", callback_data="admin_header_points")],
        [InlineKeyboardButton("➕ شحن نقاط", callback_data="admin_add_points"),
         InlineKeyboardButton("➖ سحب نقاط", callback_data="admin_remove_points")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_header_users")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban"),
         InlineKeyboardButton("✅ فك حظر", callback_data="admin_unban")],
        [InlineKeyboardButton("📋 قائمة المحظورين", callback_data="admin_banned_list")],
        [InlineKeyboardButton("🎁 روابط الهدية", callback_data="admin_header_gifts")],
        [InlineKeyboardButton("🎁 إنشاء رابط هدية", callback_data="admin_create_gift")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="admin_back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_panel")]
    ])

# ========== عرض لوحة التحكم ==========
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ عذراً، هذا الأمر مخصص للأدمن فقط.")
        return

    text = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
    """
    keyboard = get_admin_panel_keyboard()
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
    """
    keyboard = get_admin_panel_keyboard()
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
    return ADMIN_MAIN

# ========== معالجات الأزرار ==========
async def admin_add_points_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ غير مصرح.")
        return ConversationHandler.END
    await query.edit_message_text(
        "📝 أرسل معرف المستخدم وعدد النقاط المراد شحنها.\n"
        "مثال: <code>123456789 10</code>\n\n"
        "أو اضغط على /cancel للإلغاء.",
        parse_mode='HTML',
        reply_markup=get_admin_back_keyboard()
    )
    return ADMIN_AWAITING_ADD_POINTS

async def admin_add_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return ConversationHandler.END
    try:
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text("⚠️ الرجاء إدخال معرف المستخدم وعدد النقاط.", parse_mode='HTML')
            return ADMIN_AWAITING_ADD_POINTS
        user_id = int(parts[0])
        amount = int(parts[1])
        if amount <= 0:
            await update.message.reply_text("⚠️ يجب أن يكون عدد النقاط موجباً.")
            return ADMIN_AWAITING_ADD_POINTS
        user = db.db_get_user(user_id)
        if user is None:
            await update.message.reply_text(f"❌ المستخدم {user_id} غير موجود.")
            return ADMIN_AWAITING_ADD_POINTS
        db.db_add_points(user_id, amount)
        logger.info(f"Admin {update.effective_user.id} شحن {amount} نقطة للمستخدم {user_id}")
        await update.message.reply_text(
            f"✅ تم شحن <b>{amount}</b> نقطة للمستخدم <code>{user_id}</code>.\n"
            f"رصيده الحالي: <b>{user['points'] + amount}</b> نقطة.",
            parse_mode='HTML'
        )
        text = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
        """
        keyboard = get_admin_panel_keyboard()
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)
        return ADMIN_MAIN
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة.")
        return ADMIN_AWAITING_ADD_POINTS
    except Exception as e:
        logger.error(f"خطأ في شحن النقاط: {e}")
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ADMIN_AWAITING_ADD_POINTS

async def admin_remove_points_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ غير مصرح.")
        return ConversationHandler.END
    await query.edit_message_text(
        "📝 أرسل معرف المستخدم وعدد النقاط المراد سحبها.\n"
        "مثال: <code>123456789 5</code>\n\n"
        "أو اضغط على /cancel للإلغاء.",
        parse_mode='HTML',
        reply_markup=get_admin_back_keyboard()
    )
    return ADMIN_AWAITING_REMOVE_POINTS

async def admin_remove_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return ConversationHandler.END
    try:
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text("⚠️ الرجاء إدخال معرف المستخدم وعدد النقاط.", parse_mode='HTML')
            return ADMIN_AWAITING_REMOVE_POINTS
        user_id = int(parts[0])
        amount = int(parts[1])
        if amount <= 0:
            await update.message.reply_text("⚠️ يجب أن يكون عدد النقاط موجباً.")
            return ADMIN_AWAITING_REMOVE_POINTS
        user = db.db_get_user(user_id)
        if user is None:
            await update.message.reply_text(f"❌ المستخدم {user_id} غير موجود.")
            return ADMIN_AWAITING_REMOVE_POINTS
        if user['points'] < amount:
            await update.message.reply_text(f"❌ رصيد المستخدم <b>{user['points']}</b> نقطة فقط، لا يكفي للسحب.", parse_mode='HTML')
            return ADMIN_AWAITING_REMOVE_POINTS
        db.db_add_points(user_id, -amount)
        logger.info(f"Admin {update.effective_user.id} سحب {amount} نقطة من المستخدم {user_id}")
        await update.message.reply_text(
            f"✅ تم سحب <b>{amount}</b> نقطة من المستخدم <code>{user_id}</code>.\n"
            f"رصيده الحالي: <b>{user['points'] - amount}</b> نقطة.",
            parse_mode='HTML'
        )
        text = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
        """
        keyboard = get_admin_panel_keyboard()
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)
        return ADMIN_MAIN
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة.")
        return ADMIN_AWAITING_REMOVE_POINTS
    except Exception as e:
        logger.error(f"خطأ في سحب النقاط: {e}")
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ADMIN_AWAITING_REMOVE_POINTS

async def admin_create_gift_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ غير مصرح.")
        return ConversationHandler.END
    await query.edit_message_text(
        "🎁 أرسل عدد النقاط والحد الأقصى للمستفيدين.\n"
        "مثال: <code>10 5</code> (يعني 10 نقاط لأول 5 مستخدمين)\n\n"
        "أو اضغط على /cancel للإلغاء.",
        parse_mode='HTML',
        reply_markup=get_admin_back_keyboard()
    )
    return ADMIN_AWAITING_GIFT

async def admin_create_gift_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return ConversationHandler.END
    try:
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text("⚠️ الرجاء إدخال عدد النقاط والحد الأقصى للمستخدمين.", parse_mode='HTML')
            return ADMIN_AWAITING_GIFT
        points = int(parts[0])
        max_uses = int(parts[1])
        if points <= 0 or max_uses <= 0:
            await update.message.reply_text("⚠️ يجب أن تكون الأرقام موجبة.")
            return ADMIN_AWAITING_GIFT
        code = db.db_create_gift(points, max_uses)
        if not code:
            await update.message.reply_text("❌ فشل إنشاء الهدية، حاول مجدداً.")
            return ADMIN_AWAITING_GIFT
        link = f"https://t.me/{config.BOT_USERNAME}?start=gift_{code}"
        text = config.GIFT_CREATED_TEXT.format(
            points=points,
            max_uses=max_uses,
            link=link,
            code=code
        )
        logger.info(f"Admin {update.effective_user.id} أنشأ رابط هدية: {code}")
        await update.message.reply_text(text, parse_mode='HTML')
        text_panel = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
        """
        keyboard = get_admin_panel_keyboard()
        await update.message.reply_text(text_panel, parse_mode='HTML', reply_markup=keyboard)
        return ADMIN_MAIN
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة.")
        return ADMIN_AWAITING_GIFT
    except Exception as e:
        logger.error(f"خطأ في إنشاء رابط الهدية: {e}")
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ADMIN_AWAITING_GIFT

async def admin_ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ غير مصرح.")
        return ConversationHandler.END
    await query.edit_message_text(
        "🚫 أرسل معرف المستخدم المراد حظره.\n"
        "مثال: <code>123456789</code>\n\n"
        "أو اضغط على /cancel للإلغاء.",
        parse_mode='HTML',
        reply_markup=get_admin_back_keyboard()
    )
    return ADMIN_AWAITING_BAN

async def admin_ban_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return ConversationHandler.END
    try:
        user_id = int(update.message.text.strip())
        if user_id == config.ADMIN_ID:
            await update.message.reply_text("⚠️ لا يمكن حظر الأدمن نفسه.")
            return ADMIN_AWAITING_BAN
        db.db_ban_user(user_id)
        logger.info(f"Admin {update.effective_user.id} حظر المستخدم {user_id}")
        await update.message.reply_text(f"✅ تم حظر المستخدم <code>{user_id}</code> بنجاح.", parse_mode='HTML')
        text = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
        """
        keyboard = get_admin_panel_keyboard()
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)
        return ADMIN_MAIN
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال معرف مستخدم صحيح (أرقام فقط).")
        return ADMIN_AWAITING_BAN
    except Exception as e:
        logger.error(f"خطأ في حظر المستخدم: {e}")
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ADMIN_AWAITING_BAN

async def admin_unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ غير مصرح.")
        return ConversationHandler.END
    await query.edit_message_text(
        "✅ أرسل معرف المستخدم المراد فك حظره.\n"
        "مثال: <code>123456789</code>\n\n"
        "أو اضغط على /cancel للإلغاء.",
        parse_mode='HTML',
        reply_markup=get_admin_back_keyboard()
    )
    return ADMIN_AWAITING_UNBAN

async def admin_unban_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return ConversationHandler.END
    try:
        user_id = int(update.message.text.strip())
        if not db.db_is_banned(user_id):
            await update.message.reply_text(f"❌ المستخدم <code>{user_id}</code> ليس محظوراً.", parse_mode='HTML')
            return ADMIN_AWAITING_UNBAN
        db.db_unban_user(user_id)
        logger.info(f"Admin {update.effective_user.id} فك حظر المستخدم {user_id}")
        await update.message.reply_text(f"✅ تم فك الحظر عن المستخدم <code>{user_id}</code> بنجاح.", parse_mode='HTML')
        text = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
        """
        keyboard = get_admin_panel_keyboard()
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)
        return ADMIN_MAIN
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال معرف مستخدم صحيح (أرقام فقط).")
        return ADMIN_AWAITING_UNBAN
    except Exception as e:
        logger.error(f"خطأ في فك حظر المستخدم: {e}")
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ADMIN_AWAITING_UNBAN

async def admin_banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ غير مصرح.")
        return ConversationHandler.END
    banned = db.db_get_banned_list()
    if not banned:
        await query.edit_message_text("✅ لا يوجد مستخدمين محظورين حالياً.", reply_markup=get_admin_back_keyboard())
        return ADMIN_MAIN
    text = "🚫 <b>قائمة المحظورين</b>\n\n"
    for row in banned:
        text += f"• <code>{row['user_id']}</code> – منذ {row['banned_at']}\n"
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_admin_back_keyboard())
    return ADMIN_MAIN

async def admin_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ غير مصرح.")
        return ConversationHandler.END
    # استدعاء دالة start من main.py لإعادة عرض القائمة الرئيسية
    from bot.main import start
    fake_update = update
    fake_update.message = query.message
    await start(fake_update, context)
    return ConversationHandler.END

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None:
        return
    await update.message.reply_text("❌ تم إلغاء العملية.")
    text = """
<b>🔐 لوحة التحكم الإدارية</b>

اختر إحدى المجموعات أدناه لإدارة البوت:

• <b>إدارة النقاط</b>: شحن أو سحب نقاط المستخدمين.
• <b>إدارة المستخدمين</b>: حظر، فك حظر، أو عرض المحظورين.
• <b>روابط الهدية</b>: إنشاء روابط هدايا بنقاط مجانية.
    """
    keyboard = get_admin_panel_keyboard()
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)
    return ConversationHandler.END

# ========== أوامر إدارية نصية (احتياط) ==========
async def add_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None or not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ الاستخدام: /add_points <user_id> <amount>")
        return
    try:
        user_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة.")
        return
    if amount <= 0:
        await update.message.reply_text("⚠️ يجب أن يكون المبلغ موجباً.")
        return
    user = db.db_get_user(user_id)
    if user is None:
        await update.message.reply_text(f"❌ المستخدم {user_id} غير موجود.")
        return
    db.db_add_points(user_id, amount)
    await update.message.reply_text(f"✅ تم شحن {amount} نقطة للمستخدم {user_id}. رصيده الحالي: {user['points'] + amount}")

async def remove_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None or not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ الاستخدام: /remove_points <user_id> <amount>")
        return
    try:
        user_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة.")
        return
    if amount <= 0:
        await update.message.reply_text("⚠️ يجب أن يكون المبلغ موجباً.")
        return
    user = db.db_get_user(user_id)
    if user is None:
        await update.message.reply_text(f"❌ المستخدم {user_id} غير موجود.")
        return
    if user['points'] < amount:
        await update.message.reply_text(f"❌ رصيد المستخدم {user['points']} نقطة فقط، لا يكفي للسحب.")
        return
    db.db_add_points(user_id, -amount)
    await update.message.reply_text(f"✅ تم سحب {amount} نقطة من المستخدم {user_id}. رصيده الحالي: {user['points'] - amount}")

async def create_gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None or not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ الاستخدام: /create_gift <points> <max_uses>")
        return
    try:
        points = int(args[0])
        max_uses = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة.")
        return
    if points <= 0 or max_uses <= 0:
        await update.message.reply_text("⚠️ يجب أن تكون الأرقام موجبة.")
        return
    code = db.db_create_gift(points, max_uses)
    if not code:
        await update.message.reply_text("❌ فشل إنشاء الهدية.")
        return
    link = f"https://t.me/{config.BOT_USERNAME}?start=gift_{code}"
    text = config.GIFT_CREATED_TEXT.format(points=points, max_uses=max_uses, link=link, code=code)
    await update.message.reply_text(text, parse_mode='HTML')

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None or not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("⚠️ الاستخدام: /ban <user_id>")
        return
    try:
        user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال رقم صحيح.")
        return
    if user_id == config.ADMIN_ID:
        await update.message.reply_text("⚠️ لا يمكن حظر الأدمن نفسه.")
        return
    db.db_ban_user(user_id)
    await update.message.reply_text(f"✅ تم حظر المستخدم {user_id}.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None or not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("⚠️ الاستخدام: /unban <user_id>")
        return
    try:
        user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال رقم صحيح.")
        return
    if not db.db_is_banned(user_id):
        await update.message.reply_text(f"❌ المستخدم {user_id} ليس محظوراً.")
        return
    db.db_unban_user(user_id)
    await update.message.reply_text(f"✅ تم فك الحظر عن المستخدم {user_id}.")

async def banned_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None or not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح.")
        return
    banned = db.db_get_banned_list()
    if not banned:
        await update.message.reply_text("✅ لا يوجد مستخدمين محظورين حالياً.")
        return
    text = "🚫 <b>قائمة المحظورين</b>\n\n"
    for row in banned:
        text += f"• <code>{row['user_id']}</code> – منذ {row['banned_at']}\n"
    await update.message.reply_text(text, parse_mode='HTML')

# ========== إنشاء معالج المحادثة الإدارية ==========
def get_admin_conversation_handler():
    """إنشاء وإرجاع معالج المحادثة الإدارية."""
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_panel_command, pattern="^admin_panel$"),
            CallbackQueryHandler(admin_add_points_start, pattern="^admin_add_points$"),
            CallbackQueryHandler(admin_remove_points_start, pattern="^admin_remove_points$"),
            CallbackQueryHandler(admin_create_gift_start, pattern="^admin_create_gift$"),
            CallbackQueryHandler(admin_ban_start, pattern="^admin_ban$"),
            CallbackQueryHandler(admin_unban_start, pattern="^admin_unban$"),
            CallbackQueryHandler(admin_banned_list, pattern="^admin_banned_list$"),
            CallbackQueryHandler(admin_back_to_main, pattern="^admin_back_to_main$"),
        ],
        states={
            ADMIN_MAIN: [
                CallbackQueryHandler(admin_add_points_start, pattern="^admin_add_points$"),
                CallbackQueryHandler(admin_remove_points_start, pattern="^admin_remove_points$"),
                CallbackQueryHandler(admin_create_gift_start, pattern="^admin_create_gift$"),
                CallbackQueryHandler(admin_ban_start, pattern="^admin_ban$"),
                CallbackQueryHandler(admin_unban_start, pattern="^admin_unban$"),
                CallbackQueryHandler(admin_banned_list, pattern="^admin_banned_list$"),
                CallbackQueryHandler(admin_back_to_main, pattern="^admin_back_to_main$"),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_cancel, pattern="^admin_cancel$"),
            ],
            ADMIN_AWAITING_ADD_POINTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_points_input),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_cancel, pattern="^admin_cancel$"),
            ],
            ADMIN_AWAITING_REMOVE_POINTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_remove_points_input),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_cancel, pattern="^admin_cancel$"),
            ],
            ADMIN_AWAITING_GIFT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_gift_input),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_cancel, pattern="^admin_cancel$"),
            ],
            ADMIN_AWAITING_BAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_input),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_cancel, pattern="^admin_cancel$"),
            ],
            ADMIN_AWAITING_UNBAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unban_input),
                CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_cancel, pattern="^admin_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin_cancel),
            CallbackQueryHandler(show_admin_panel, pattern="^admin_panel$"),
            CallbackQueryHandler(admin_cancel, pattern="^admin_cancel$"),
        ],
        per_message=False,
        per_chat=True,
        allow_reentry=True,
        name="admin_conversation",
    )
    return conv_handler