# bot/main.py
# [+] الملف الرئيسي للمعالجات - تم تحسين معالجة الأخطاء والنصوص

import logging
import time
import asyncio
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import config
from bot import database as db
from bot import grok_api
from bot import keyboards
from bot import admin

logger = logging.getLogger(__name__)

# ============================================================
# [+] تحديد معدل الطلبات (في الذاكرة - مقبول لبيئة فيرسل مع بعض القيود)
# ============================================================

_rate_limit_cache: Dict[int, list] = {}
RATE_LIMIT_WINDOW: int = 10
RATE_LIMIT_MAX: int = 5

def check_rate_limit(user_id: int) -> bool:
    """[+] التحقق من عدم تجاوز حد الطلبات"""
    now = time.time()
    if user_id not in _rate_limit_cache:
        _rate_limit_cache[user_id] = []
    _rate_limit_cache[user_id] = [t for t in _rate_limit_cache[user_id] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_cache[user_id]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_cache[user_id].append(now)
    return True

# ============================================================
# [+] التحقق من الاشتراك مع تخزين مؤقت (محلي)
# ============================================================

_subscription_cache: Dict[int, Dict[str, Any]] = {}
CACHE_TTL: int = 30

async def check_subscription(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """[+] التحقق من اشتراك المستخدم في القناة"""
    now = time.time()
    if chat_id in _subscription_cache:
        cached = _subscription_cache[chat_id]
        if now - cached["timestamp"] < CACHE_TTL:
            return cached["status"]
    try:
        member = await context.bot.get_chat_member(config.CHANNEL_ID, chat_id)
        status = member.status in ["member", "administrator", "creator"]
    except Exception:
        status = False
    _subscription_cache[chat_id] = {"status": status, "timestamp": now}
    return status

# ============================================================
# [+] دالة مساعدة لتعديل النص بأمان
# ============================================================

async def safe_edit_caption(query, caption: str, reply_markup=None) -> None:
    """[+] تعديل النص بأمان مع التعامل مع الحالات المختلفة"""
    try:
        if query.message.caption is None:
            await query.message.reply_photo(
                photo=config.MAIN_IMAGE_URL,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            try:
                await query.message.delete()
            except Exception:
                pass
            return
        current_caption = query.message.caption or ""
        current_markup = query.message.reply_markup
        if current_caption == caption and current_markup == reply_markup:
            return
        await query.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        elif "There is no caption" in str(e):
            try:
                await query.message.reply_photo(
                    photo=config.MAIN_IMAGE_URL,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                await query.message.delete()
            except Exception:
                pass
        else:
            raise

# ============================================================
# [+] معالج البدء
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[+] معالج أمر /start"""
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    args = context.args

    if not check_rate_limit(user_id):
        await update.message.reply_text("[!] وصلت للحد الأقصى من الطلبات. يرجى الانتظار قليلاً.")
        return

    if db.db_is_banned(user_id):
        await update.message.reply_text("[x] لا يمكنك استخدام هذا البوت حالياً.")
        return

    # [+] معالجة معلمات الديب لينك
    if args:
        param = args[0]
        if param.startswith("ref_"):
            invited_by = param.split("_")[1]
            if invited_by.isdigit():
                invited_by = int(invited_by)
                user_data = db.db_get_user(user_id)
                if user_data is None:
                    db.db_add_user(user_id, invited_by)
                    try:
                        await context.bot.send_message(
                            chat_id=invited_by,
                            text="[+] قام صديقك بالاشتراك عبر رابطك! حصلت على نقطة إضافية."
                        )
                    except Exception:
                        pass
                    await update.message.reply_text("[+] تم تفعيل حسابك! حصلت على نقطة مجانية، وصديقك حصل على نقطة أيضاً.")
                else:
                    await update.message.reply_text("[=] هذا الرابط خاص بالدعوة، لكنك مسجل بالفعل.")
            else:
                await update.message.reply_text("[?] رابط دعوة غير صالح.")
            return
        elif param.startswith("gift_"):
            code = param.split("_")[1]
            gift = db.db_get_gift(code)
            if not gift:
                await update.message.reply_text("[?] رابط هدية غير صالح.")
                return
            if gift.get('used_count', 0) >= gift.get('max_uses', 0):
                await update.message.reply_text(config.GIFT_ALREADY_USED)
                return
            result = db.db_use_gift(code)
            if result == "expired":
                await update.message.reply_text(config.GIFT_ALREADY_USED)
                return
            db.db_add_points(user_id, gift['points'])
            await update.message.reply_text(
                config.GIFT_SUCCESS_TEXT.format(points=gift['points'], code=code),
                parse_mode='HTML'
            )
            return

    # [+] التحقق من الاشتراك
    if not await check_subscription(user_id, context):
        caption = config.SUB_REQUIRED_TEXT
        keyboard = keyboards.subscription_check_keyboard()
        await update.message.reply_photo(
            photo=config.SUBSCRIPTION_IMAGE_URL,
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return

    # [+] إنشاء المستخدم إذا لم يكن موجوداً
    user_data = db.db_get_user(user_id)
    if user_data is None:
        db.db_add_user(user_id, None)
        await update.message.reply_text("[+] مرحباً بك! حصلت على نقطة مجانية للبدء.")

    caption = config.WELCOME_TEXT
    keyboard = keyboards.main_menu_keyboard()
    await update.message.reply_photo(
        photo=config.MAIN_IMAGE_URL,
        caption=caption,
        reply_markup=keyboard,
        parse_mode='HTML'
    )

# ============================================================
# [+] معالج زر استخراج البرومبت
# ============================================================

async def extract_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[+] معالج الضغط على زر استخراج البرومبت"""
    if update.effective_user is None:
        return
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not check_rate_limit(user_id):
        await query.answer("[!] وصلت للحد الأقصى من الطلبات.", show_alert=True)
        return

    if db.db_is_banned(user_id):
        await query.edit_message_caption("[x] لا يمكنك استخدام هذه الميزة.")
        return

    if not await check_subscription(user_id, context):
        caption = config.SUB_REQUIRED_TEXT
        keyboard = keyboards.subscription_check_keyboard()
        await safe_edit_caption(query, caption, keyboard)
        return

    user_data = db.db_get_user(user_id)
    if user_data is None or user_data.get('points', 0) < 1:
        invite_link = db.get_invite_link(user_id)
        caption = config.NO_POINTS_TEXT.format(invite_link=invite_link)
        back_keyboard = keyboards.back_keyboard()
        await safe_edit_caption(query, caption, back_keyboard)
        return

    if context.user_data.get("awaiting_image"):
        await query.answer("[~] أنت بالفعل في حالة انتظار.", show_alert=True)
        return

    context.user_data["awaiting_image"] = True
    cancel_keyboard = keyboards.cancel_keyboard()
    await safe_edit_caption(query, config.REQUEST_IMAGE_TEXT, cancel_keyboard)

# ============================================================
# [+] معالج استلام الصور
# ============================================================

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[+] معالج استلام الصور لاستخراج البرومبت"""
    logger.info("[+] دالة handle_image تم استدعاؤها")
    if update.effective_user is None:
        logger.warning("[!] التحديث لا يحتوي على مستخدم")
        return
    user_id = update.effective_user.id

    if not check_rate_limit(user_id):
        await update.message.reply_text("[!] وصلت للحد الأقصى من الطلبات.")
        return

    if db.db_is_banned(user_id):
        await update.message.reply_text("[x] لا يمكنك استخدام هذه الميزة.")
        return

    if not context.user_data.get("awaiting_image"):
        await update.message.reply_text("[?] الرجاء إرسال /start أولاً.")
        return

    if not update.message.photo:
        await update.message.reply_text("[?] يرجى إرسال صورة واحدة فقط.")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    if file.file_size > config.MAX_IMAGE_SIZE:
        await update.message.reply_text(
            f"[!] حجم الصورة كبير جداً (الحد {config.MAX_IMAGE_SIZE//1024//1024} ميجابايت)."
        )
        context.user_data["awaiting_image"] = False
        return

    user_data = db.db_get_user(user_id)
    if user_data is None or user_data.get('points', 0) < 1:
        await update.message.reply_text("[x] لا تملك نقاطاً كافية.")
        context.user_data["awaiting_image"] = False
        return

    # [+] خصم نقطة
    db.db_add_points(user_id, -1)
    image_bytes = await file.download_as_bytearray()

    queue_msg = await update.message.reply_text("[~] جاري تحليل الصورة... قد يستغرق 10-30 ثانية.")
    context.user_data["awaiting_image"] = False

    try:
        # [+] الحصول على جلسة Grok
        token, chat_uuid = grok_api.get_grok_session()
        
        # [+] رفع الصورة
        image_url = grok_api.upload_image_to_grok(chat_uuid, image_bytes, token)
        
        # [+] إرسال الطلب
        objects = [
            {"object_type": "text", "object_url": None, "object_text": config.SYSTEM_PROMPT, "model_type": "grok-4.5"},
            {"object_type": "image", "object_url": image_url, "object_text": "صورة", "model_type": "grok-4.5"}
        ]
        msg_id = grok_api.send_message_to_grok(chat_uuid, objects, token)
        reply_text = grok_api.wait_for_reply(chat_uuid, msg_id, token, timeout=25)

        # [+] إرسال النتيجة للمستخدم
        await queue_msg.delete()
        await context.bot.send_message(chat_id=user_id, text=reply_text)
        await context.bot.send_message(chat_id=user_id, text="/start")

        # [+] نشر في قناة الترويج (مع تجاهل الأخطاء)
        try:
            await context.bot.send_photo(chat_id=config.PROMO_CHANNEL_ID, photo=image_bytes, caption="[+] بواسطة @UFOQ_BOT")
            await context.bot.send_message(chat_id=config.PROMO_CHANNEL_ID, text=reply_text)
        except Exception:
            pass

    except Exception as e:
        await queue_msg.delete()
        error_msg = str(e)[:200]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"[x] حدث خطأ أثناء معالجة الصورة: {error_msg}\n\n[>] يرجى المحاولة مرة أخرى لاحقاً."
        )

# ============================================================
# [+] معالج إلغاء الاستخراج
# ============================================================

async def cancel_extract(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[+] إلغاء عملية استخراج البرومبت"""
    if update.effective_user is None:
        return
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_image"] = False
    caption = config.WELCOME_TEXT
    keyboard = keyboards.main_menu_keyboard()
    await safe_edit_caption(query, caption, keyboard)

# ============================================================
# [+] معالج أمر الإلغاء
# ============================================================

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[+] أمر /cancel"""
    if update.effective_user is None:
        return
    context.user_data["awaiting_image"] = False
    await update.message.reply_text("[x] تم إلغاء العملية.")
    caption = config.WELCOME_TEXT
    keyboard = keyboards.main_menu_keyboard()
    await update.message.reply_photo(
        photo=config.MAIN_IMAGE_URL,
        caption=caption,
        reply_markup=keyboard,
        parse_mode='HTML'
    )

# ============================================================
# [+] معالج الاستعلامات الأخرى
# ============================================================

async def other_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[+] معالج جميع استعلامات رد الاتصال الأخرى"""
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
        await update.callback_query.answer("[!] وصلت للحد الأقصى من الطلبات.", show_alert=True)
        return
    query = update.callback_query
    await query.answer()

    if db.db_is_banned(user_id):
        if query.message.caption is not None:
            await query.edit_message_caption("[x] لا يمكنك استخدام هذه الميزة.")
        else:
            await query.message.reply_text("[x] لا يمكنك استخدام هذه الميزة.")
        return

    if not await check_subscription(user_id, context):
        caption = config.SUB_REQUIRED_TEXT
        keyboard = keyboards.subscription_check_keyboard()
        await safe_edit_caption(query, caption, keyboard)
        return

    data = query.data
    
    # [+] عرض نظام النقاط
    if data == "points":
        user_data = db.db_get_user(user_id)
        if user_data:
            points = user_data.get('points', 0)
            invited_count = user_data.get('invite_count', 0)
            invite_link = db.get_invite_link(user_id)
            text = config.POINTS_INFO_TEXT.format(
                invite_link=invite_link,
                invited_count=invited_count,
                points=points
            )
            keyboard = keyboards.points_menu_keyboard()
            await safe_edit_caption(query, text, keyboard)
        else:
            await safe_edit_caption(query, "[x] حدث خطأ في استرجاع بياناتك.", keyboards.points_menu_keyboard())
    
    # [+] عرض معلومات الدعوة
    elif data == "invite":
        user_data = db.db_get_user(user_id)
        if user_data:
            invite_link = db.get_invite_link(user_id)
            text = f"""
[*] رابط الدعوة الخاص بك [*]

[+] انسخ الرابط وأرسله لأصدقائك:
<code>{invite_link}</code>

[#] كل دعوة ناجحة تمنحك نقطة إضافية.
[#] عدد المدعوين الحالي: {user_data.get('invite_count', 0)}

[>] شارك الرابط الآن واجمع النقاط!
"""
            keyboard = keyboards.invite_keyboard()
            await safe_edit_caption(query, text, keyboard)
        else:
            await safe_edit_caption(query, "[x] حدث خطأ في استرجاع بياناتك.", keyboards.back_keyboard())
    
    # [+] عرض معلومات المطور
    elif data == "developer":
        text = config.DEVELOPER_TEXT
        keyboard = keyboards.developer_keyboard()
        await safe_edit_caption(query, text, keyboard)
    
    # [+] العودة للقائمة الرئيسية
    elif data == "back_to_main":
        context.user_data["awaiting_image"] = False
        caption = config.WELCOME_TEXT
        keyboard = keyboards.main_menu_keyboard()
        await safe_edit_caption(query, caption, keyboard)
    
    # [+] التحقق من الاشتراك
    elif data == "check_sub":
        if user_id in _subscription_cache:
            del _subscription_cache[user_id]
        if await check_subscription(user_id, context):
            caption = "[+] تم التحقق من اشتراكك!"
            keyboard = keyboards.main_menu_keyboard()
            await safe_edit_caption(query, caption, keyboard)
        else:
            caption = "[x] لا يزال الاشتراك غير مفعّل."
            await safe_edit_caption(query, caption, keyboards.subscription_check_keyboard())

# ============================================================
# [+] معالج الأخطاء العام
# ============================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[+] معالج الأخطاء غير المتوقعة"""
    logger.error(f"[x] خطأ غير متوقع: {context.error}", exc_info=True)
    if update and update.effective_message and update.effective_user:
        try:
            await update.effective_message.reply_text(
                "[x] عذراً، حدث خطأ غير متوقع.\n\n[>] يرجى المحاولة مرة أخرى أو التواصل مع المطور."
            )
        except Exception as e:
            logger.error(f"[x] تعذر إرسال رسالة الخطأ: {e}")