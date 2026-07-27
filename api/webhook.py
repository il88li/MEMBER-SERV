import sys
import os
import json
import logging
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import config
import database as db
import grok_api
import keyboards
import admin
from bot.main import (
    start, extract_button, handle_image, cancel_extract,
    cancel_command, other_callbacks, error_handler
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# تهيئة التطبيق (متغير على المستوى الأعلى)
# ============================================================

app = Application.builder().token(config.BOT_TOKEN).build()

# تسجيل المعالجات
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("cancel", cancel_command))

# أوامر الإدارة النصية
app.add_handler(CommandHandler("admin", admin.admin_panel_command))
app.add_handler(CommandHandler("add_points", admin.add_points_command))
app.add_handler(CommandHandler("remove_points", admin.remove_points_command))
app.add_handler(CommandHandler("create_gift", admin.create_gift_command))
app.add_handler(CommandHandler("ban", admin.ban_command))
app.add_handler(CommandHandler("unban", admin.unban_command))
app.add_handler(CommandHandler("banned_list", admin.banned_list_command))

# معالج المحادثة الإدارية
app.add_handler(admin.get_admin_conversation_handler())

# أزرار المستخدم
app.add_handler(CallbackQueryHandler(extract_button, pattern="^extract$"))
app.add_handler(CallbackQueryHandler(cancel_extract, pattern="^cancel_extract$"))
app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_image))
app.add_handler(CallbackQueryHandler(other_callbacks, pattern="^(?!extract$|cancel_extract$|admin_).*$"))

# معالج الأخطاء
app.add_error_handler(error_handler)

# تهيئة قاعدة البيانات
db.init_db()

# ============================================================
# نقطة الدخول من Vercel
# ============================================================

async def handler(request):
    """وظيفة المعالجة لـ Vercel - يجب أن تُسمى 'handler'."""
    if request.method == "POST":
        try:
            body = await request.json()
            logger.info(f"📩 تحديث: {body.get('update_id', 'unknown')}")
            update = Update.de_json(body, app.bot)
            # معالجة التحديث بشكل متزامن
            await app.process_update(update)
            return {"ok": True}
        except Exception as e:
            logger.error(f"❌ خطأ: {e}", exc_info=True)
            return {"error": str(e)}, 500
    else:
        return {"status": "ok", "message": "UFOQ Bot is running"}, 200

# للتوافق مع Vercel (أسماء محتملة)
webhook = handler