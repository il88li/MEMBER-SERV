import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

import config
import database
import grok_api
import keyboards
import admin
from bot.main import (
    start, extract_button, handle_image, cancel_extract, 
    cancel_command, other_callbacks, error_handler,
    check_subscription, safe_edit_caption, process_analysis_task
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def webhook(request):
    """نقطة دخول Vercel"""
    if request.method == "POST":
        body = await request.json()
        update = Update.de_json(body, None)
        
        # تطبيق البوت
        app = Application.builder().token(config.BOT_TOKEN).build()
        
        # تسجيل المعالجات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("cancel", cancel_command))
        app.add_handler(CommandHandler("admin", admin.admin_panel_command))
        app.add_handler(CommandHandler("add_points", admin.add_points_command))
        app.add_handler(CommandHandler("remove_points", admin.remove_points_command))
        app.add_handler(CommandHandler("create_gift", admin.create_gift_command))
        app.add_handler(CommandHandler("ban", admin.ban_command))
        app.add_handler(CommandHandler("unban", admin.unban_command))
        app.add_handler(CommandHandler("banned_list", admin.banned_list_command))
        app.add_handler(admin.get_admin_conversation_handler())
        app.add_handler(CallbackQueryHandler(extract_button, pattern="^extract$"))
        app.add_handler(CallbackQueryHandler(cancel_extract, pattern="^cancel_extract$"))
        app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_image))
        app.add_handler(CallbackQueryHandler(other_callbacks, pattern="^(?!extract$|cancel_extract$|admin_).*$"))
        app.add_error_handler(error_handler)
        
        # تهيئة القاعدة بيانات
        database.init_db()
        
        await app.initialize()
        await app.process_update(update)
        await app.shutdown()
        
        return {"ok": True}
    
    return {"error": "Method not allowed"}, 405