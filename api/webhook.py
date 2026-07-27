# api/webhook.py
# [+] نقطة دخول Vercel باستخدام Flask (متوافق مع WSGI)

import sys
import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify

# [+] إعداد مسار الاستيراد
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot import config
from bot import database as db
import bot.grok_api
from bot import keyboards
from bot import admin
from bot.main import (
    start, extract_button, handle_image, cancel_extract,
    cancel_command, other_callbacks, error_handler
)

# [+] تهيئة التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# [+] تهيئة تطبيق البوت (غير متزامن)
# ============================================================

_app_instance = None

def get_app() -> Application:
    """[+] تهيئة كسولة لتطبيق البوت"""
    global _app_instance
    if _app_instance is None:
        app = Application.builder().token(config.BOT_TOKEN).build()
        
        # [+] إضافة المعالجات
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
        
        db.init_db()
        logger.info("[+] تم تهيئة تطبيق البوت بنجاح")
        _app_instance = app
    return _app_instance

# ============================================================
# [+] تعيين Webhook باستخدام Flask (مرة واحدة)
# ============================================================

def set_webhook_if_needed():
    """[+] تعيين webhook عند أول طلب فقط"""
    import requests
    webhook_url = "https://member-serv.vercel.app/api/webhook"
    api_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook"
    
    try:
        # [+] التحقق من الوضع الحالي
        check_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getWebhookInfo"
        check_resp = requests.get(check_url, timeout=5)
        if check_resp.status_code == 200:
            info = check_resp.json()
            if info.get("ok") and info.get("result", {}).get("url") == webhook_url:
                logger.info("[=] Webhook مُعيّن بالفعل")
                return
        
        # [+] تعيين webhook
        resp = requests.post(api_url, json={"url": webhook_url}, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info(f"[+] تم تعيين Webhook إلى {webhook_url}")
        else:
            logger.error(f"[-] فشل تعيين Webhook: {resp.text}")
    except Exception as e:
        logger.error(f"[-] خطأ في تعيين Webhook: {e}")

# ============================================================
# [+] إنشاء تطبيق Flask
# ============================================================

flask_app = Flask(__name__)

@flask_app.route("/api/webhook", methods=["POST"])
def webhook_handler():
    """[+] نقطة استقبال Webhook من Telegram"""
    try:
        # [+] تعيين Webhook (مرة واحدة)
        set_webhook_if_needed()
        
        # [+] الحصول على بيانات الطلب
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        logger.info(f"[+] تحديث وارد: {data.get('update_id', 'unknown')}")
        
        # [+] تهيئة التطبيق
        app = get_app()
        
        # [+] معالجة التحديث (غير متزامن، نستخدم asyncio.run)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            update = Update.de_json(data, app.bot)
            loop.run_until_complete(app.process_update(update))
        finally:
            loop.close()
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        logger.error(f"[-] خطأ في معالجة الطلب: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/webhook", methods=["GET"])
def health_check():
    """[+] نقطة للتحقق من صحة التطبيق"""
    return jsonify({"status": "ok", "message": "UFOQ Bot is running"}), 200

@flask_app.route("/", methods=["GET"])
def root():
    """[+] الصفحة الرئيسية"""
    return jsonify({"status": "ok", "message": "UFOQ Bot is running"}), 200

# ============================================================
# [+] تصدير التطبيق لـ Vercel
# ============================================================

# [+] Vercel يتوقع متغيراً باسم `app` لتطبيقات WSGI
app = flask_app

# [+] للتوافق مع الإصدارات القديمة
webhook = flask_app