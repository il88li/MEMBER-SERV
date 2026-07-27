# api/webhook.py
# [+] نقطة دخول Vercel باستخدام Flask - نسخة نهائية مع دعم Webhook

import sys
import os
import json
import logging
import asyncio
import requests
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

def get_app():
    """[+] تهيئة كسولة لتطبيق البوت"""
    global _app_instance
    if _app_instance is None:
        app = Application.builder().token(config.BOT_TOKEN).build()
        
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
# [+] تعيين Webhook تلقائياً
# ============================================================

WEBHOOK_SET = False

def set_webhook_force():
    """[+] تعيين Webhook بقوة - يتجاوز أي إعداد سابق"""
    global WEBHOOK_SET
    if WEBHOOK_SET:
        return True
    
    webhook_url = "https://ufoqai.vercel.app/api/webhook"
    api_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook"
    
    try:
        # [+] أولاً: حذف أي Webhook قديم
        requests.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook", timeout=5)
        
        # [+] ثانياً: تعيين Webhook الجديد
        resp = requests.post(api_url, json={"url": webhook_url}, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info(f"[+] تم تعيين Webhook إلى {webhook_url}")
            WEBHOOK_SET = True
            return True
        else:
            logger.error(f"[-] فشل تعيين Webhook: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"[-] خطأ في تعيين Webhook: {e}")
        return False

# ============================================================
# [+] إنشاء تطبيق Flask
# ============================================================

flask_app = Flask(__name__)

@flask_app.route("/api/webhook", methods=["POST"])
def webhook_handler():
    """[+] نقطة استقبال Webhook من Telegram"""
    try:
        # [+] تعيين Webhook تلقائياً عند أول طلب
        set_webhook_force()
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        logger.info(f"[+] تحديث وارد: {data.get('update_id', 'unknown')}")
        
        app = get_app()
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
def webhook_get():
    """[+] نقطة GET للتحقق من الصحة"""
    return jsonify({
        "status": "ok", 
        "message": "UFOQ Bot is running",
        "webhook_status": "Set webhook manually via /api/set_webhook"
    }), 200

@flask_app.route("/", methods=["GET"])
def root():
    """[+] الصفحة الرئيسية"""
    return jsonify({
        "status": "ok", 
        "message": "UFOQ Bot is running",
        "endpoints": {
            "webhook": "/api/webhook (POST)",
            "set_webhook": "/api/set_webhook (GET)",
            "webhook_info": "/api/webhook_info (GET)",
            "delete_webhook": "/api/delete_webhook (GET)"
        }
    }), 200

# ============================================================
# [+] نقاط نهاية إضافية للتحكم في Webhook
# ============================================================

@flask_app.route("/api/set_webhook", methods=["GET"])
def set_webhook_manual():
    """[+] تعيين Webhook يدوياً عبر المتصفح"""
    webhook_url = "https://ufoqai.vercel.app/api/webhook"
    api_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook"
    
    try:
        # [+] حذف القديم أولاً
        requests.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook", timeout=5)
        
        # [+] تعيين الجديد
        resp = requests.post(api_url, json={"url": webhook_url}, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            return jsonify({
                "status": "success",
                "message": f"Webhook set to {webhook_url}",
                "response": resp.json()
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to set webhook",
                "response": resp.text
            }), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@flask_app.route("/api/webhook_info", methods=["GET"])
def webhook_info():
    """[+] عرض معلومات Webhook الحالية"""
    api_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getWebhookInfo"
    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            return jsonify(resp.json()), 200
        else:
            return jsonify({"error": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/delete_webhook", methods=["GET"])
def delete_webhook():
    """[+] حذف Webhook الحالي"""
    api_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook"
    try:
        resp = requests.post(api_url, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            return jsonify({"status": "success", "message": "Webhook deleted"}), 200
        else:
            return jsonify({"error": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# [+] تصدير التطبيق لـ Vercel
# ============================================================

app = flask_app
webhook = flask_app