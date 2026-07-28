# api/webhook.py
# [+] نقطة دخول Vercel مع تسجيل مفصل وتعيين Webhook يدوي

import sys
import os
import json
import logging
import asyncio
import requests
import time
from flask import Flask, request, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot import config, database as db, grok_api, keyboards, admin
from bot.main import (
    start, extract_button, handle_image, cancel_extract,
    cancel_command, other_callbacks, error_handler
)

# [+] تهيئة التسجيل مع مستوى DEBUG لمشاهدة كل التفاصيل
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# [+] متغيرات التحكم
# ============================================================

WEBHOOK_URL = "https://ufoqai.vercel.app/api/webhook"
_webhook_set = False

# ============================================================
# [+] تهيئة البوت
# ============================================================

_app_bot = None

def get_bot_app():
    global _app_bot
    if _app_bot is None:
        logger.info("[+] بدء تهيئة تطبيق البوت...")
        _app_bot = Application.builder().token(config.BOT_TOKEN).build()
        _app_bot.add_handler(CommandHandler("start", start))
        _app_bot.add_handler(CommandHandler("cancel", cancel_command))
        _app_bot.add_handler(CommandHandler("admin", admin.admin_panel_command))
        _app_bot.add_handler(CommandHandler("add_points", admin.add_points_command))
        _app_bot.add_handler(CommandHandler("remove_points", admin.remove_points_command))
        _app_bot.add_handler(CommandHandler("create_gift", admin.create_gift_command))
        _app_bot.add_handler(CommandHandler("ban", admin.ban_command))
        _app_bot.add_handler(CommandHandler("unban", admin.unban_command))
        _app_bot.add_handler(CommandHandler("banned_list", admin.banned_list_command))
        _app_bot.add_handler(admin.get_admin_conversation_handler())
        _app_bot.add_handler(CallbackQueryHandler(extract_button, pattern="^extract$"))
        _app_bot.add_handler(CallbackQueryHandler(cancel_extract, pattern="^cancel_extract$"))
        _app_bot.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_image))
        _app_bot.add_handler(CallbackQueryHandler(other_callbacks, pattern="^(?!extract$|cancel_extract$|admin_).*$"))
        _app_bot.add_error_handler(error_handler)
        db.init_db()
        logger.info("[+] تم تهيئة تطبيق البوت بنجاح")
    return _app_bot

# ============================================================
# [+] دالة تعيين Webhook مع تسجيل مفصل
# ============================================================

def set_webhook_manually():
    """[+] تعيين Webhook مع تسجيل كل خطوة"""
    global _webhook_set
    logger.info("[~] بدء تعيين Webhook...")
    
    try:
        # [+] 1. حذف Webhook القديم
        logger.info("[~] حذف Webhook القديم...")
        delete_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook"
        del_resp = requests.post(delete_url, timeout=10)
        logger.info(f"[=] رد الحذف: {del_resp.status_code} - {del_resp.text[:200]}")
        
        # [+] 2. تعيين Webhook الجديد
        logger.info(f"[~] تعيين Webhook إلى {WEBHOOK_URL}...")
        set_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook"
        set_resp = requests.post(set_url, json={"url": WEBHOOK_URL}, timeout=10)
        logger.info(f"[=] رد التعيين: {set_resp.status_code} - {set_resp.text[:200]}")
        
        if set_resp.status_code == 200:
            data = set_resp.json()
            if data.get("ok"):
                _webhook_set = True
                logger.info("[+] تم تعيين Webhook بنجاح!")
                return True
            else:
                logger.error(f"[-] فشل تعيين Webhook: {data}")
                return False
        else:
            logger.error(f"[-] فشل تعيين Webhook: HTTP {set_resp.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"[-] استثناء في تعيين Webhook: {e}", exc_info=True)
        return False

# ============================================================
# [+] تطبيق Flask
# ============================================================

flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def home():
    """[+] الصفحة الرئيسية - تعيين Webhook تلقائياً عند الزيارة"""
    logger.info("[~] طلب GET إلى /")
    result = set_webhook_manually()
    return jsonify({
        "status": "ok",
        "message": "UFOQ Bot is running",
        "webhook_set": result,
        "webhook_url": WEBHOOK_URL
    }), 200

@flask_app.route("/api/set_webhook", methods=["GET"])
def set_webhook_endpoint():
    """[+] نقطة مخصصة لتعيين Webhook يدوياً"""
    logger.info("[~] طلب GET إلى /api/set_webhook")
    result = set_webhook_manually()
    return jsonify({
        "status": "success" if result else "failed",
        "webhook_set": result,
        "webhook_url": WEBHOOK_URL,
        "message": "Webhook set successfully" if result else "Webhook setting failed"
    }), 200 if result else 500

@flask_app.route("/api/webhook_info", methods=["GET"])
def webhook_info():
    """[+] عرض معلومات Webhook الحالية"""
    logger.info("[~] طلب GET إلى /api/webhook_info")
    try:
        info_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getWebhookInfo"
        resp = requests.get(info_url, timeout=10)
        return jsonify(resp.json()), 200
    except Exception as e:
        logger.error(f"[-] خطأ في جلب معلومات Webhook: {e}")
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/webhook", methods=["POST"])
def webhook_handler():
    """[+] استقبال تحديثات Telegram"""
    logger.info("[~] طلب POST إلى /api/webhook")
    try:
        # [+] التأكد من تعيين Webhook (محاولة مرة أخرى)
        if not _webhook_set:
            set_webhook_manually()
        
        data = request.get_json()
        if not data:
            logger.warning("[-] بيانات JSON غير صالحة")
            return jsonify({"error": "Invalid JSON"}), 400
        
        logger.info(f"[+] تحديث وارد: {data.get('update_id', 'unknown')}")
        
        bot = get_bot_app()
        update = Update.de_json(data, bot.bot)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot.process_update(update))
        finally:
            loop.close()
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        logger.error(f"[-] خطأ في معالجة الطلب: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ============================================================
# [+] تصدير التطبيق
# ============================================================

app = flask_app
logger.info("[+] تم تحميل تطبيق Flask بنجاح")