# api/webhook.py
# [+] نقطة دخول Vercel مع Webhook تلقائي بالكامل

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# [+] متغيرات التحكم في Webhook
# ============================================================

_webhook_status = {
    "is_set": False,
    "last_check": 0,
    "url": ""
}

WEBHOOK_CHECK_INTERVAL = 300  # 5 دقائق بين كل فحص
WEBHOOK_URL = "https://ufoqai.vercel.app/api/webhook"

# ============================================================
# [+] تهيئة البوت
# ============================================================

_app_bot = None

def get_bot_app():
    """[+] تهيئة تطبيق البوت (مرة واحدة)"""
    global _app_bot
    if _app_bot is None:
        _app_bot = Application.builder().token(config.BOT_TOKEN).build()
        
        # [+] إضافة المعالجات
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
# [+] دوال إدارة Webhook التلقائية
# ============================================================

def ensure_webhook():
    """[+] يتحقق من Webhook ويعيد تعيينه إذا لزم الأمر"""
    global _webhook_status
    
    now = time.time()
    
    # [+] إذا مر وقت كافٍ منذ آخر فحص
    if now - _webhook_status["last_check"] < WEBHOOK_CHECK_INTERVAL and _webhook_status["is_set"]:
        return True
    
    logger.info("[~] جاري التحقق من حالة Webhook...")
    
    try:
        # [+] 1. الحصول على حالة Webhook الحالية
        info_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getWebhookInfo"
        resp = requests.get(info_url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                current_url = data.get("result", {}).get("url")
                
                # [+] إذا كان Webhook صحيحاً بالفعل
                if current_url == WEBHOOK_URL:
                    _webhook_status["is_set"] = True
                    _webhook_status["last_check"] = now
                    _webhook_status["url"] = current_url
                    logger.info("[=] Webhook مُعيّن بالفعل بشكل صحيح")
                    return True
                
                # [+] إذا كان Webhook مختلفاً أو غير موجود
                logger.info(f"[~] Webhook الحالي: {current_url} - جاري التصحيح...")
        
        # [+] 2. حذف Webhook القديم (إن وجد)
        delete_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook"
        requests.post(delete_url, timeout=5)
        
        # [+] 3. تعيين Webhook الجديد
        set_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook"
        resp = requests.post(set_url, json={"url": WEBHOOK_URL}, timeout=10)
        
        if resp.status_code == 200 and resp.json().get("ok"):
            _webhook_status["is_set"] = True
            _webhook_status["last_check"] = now
            _webhook_status["url"] = WEBHOOK_URL
            logger.info(f"[+] تم تعيين Webhook تلقائياً إلى {WEBHOOK_URL}")
            return True
        else:
            logger.error(f"[-] فشل تعيين Webhook: {resp.text}")
            _webhook_status["is_set"] = False
            _webhook_status["last_check"] = now
            return False
            
    except Exception as e:
        logger.error(f"[-] خطأ في التحقق من Webhook: {e}")
        _webhook_status["last_check"] = now
        return False

# ============================================================
# [+] تطبيق Flask
# ============================================================

flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def home():
    """[+] الصفحة الرئيسية"""
    return jsonify({
        "status": "ok",
        "message": "UFOQ Bot is running",
        "webhook_status": "automatic",
        "webhook_url": WEBHOOK_URL,
        "is_set": _webhook_status["is_set"]
    }), 200

@flask_app.route("/api/webhook", methods=["POST"])
def webhook_handler():
    """[+] نقطة استقبال Webhook من Telegram"""
    try:
        # [+] تأكد من تعيين Webhook (تلقائياً)
        ensure_webhook()
        
        # [+] استلام البيانات
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        logger.info(f"[+] تحديث وارد: {data.get('update_id', 'unknown')}")
        
        # [+] معالجة التحديث
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

@flask_app.route("/api/webhook", methods=["GET"])
def webhook_get():
    """[+] نقطة GET للتحقق من الصحة"""
    return jsonify({
        "status": "ok",
        "message": "Webhook endpoint is active",
        "webhook_url": WEBHOOK_URL,
        "is_set": _webhook_status["is_set"]
    }), 200

# ============================================================
# [+] نقاط نهاية للتحكم اليدوي (احتياطي)
# ============================================================

@flask_app.route("/api/set_webhook", methods=["GET"])
def set_webhook_manual():
    """[+] تعيين Webhook يدوياً (احتياطي)"""
    try:
        # [+] حذف القديم
        requests.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook", timeout=5)
        
        # [+] تعيين الجديد
        resp = requests.post(
            f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook",
            json={"url": WEBHOOK_URL},
            timeout=10
        )
        
        if resp.status_code == 200 and resp.json().get("ok"):
            _webhook_status["is_set"] = True
            _webhook_status["last_check"] = time.time()
            _webhook_status["url"] = WEBHOOK_URL
            return jsonify({
                "status": "success",
                "message": f"Webhook set to {WEBHOOK_URL}",
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
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{config.BOT_TOKEN}/getWebhookInfo",
            timeout=10
        )
        if resp.status_code == 200:
            return jsonify(resp.json()), 200
        else:
            return jsonify({"error": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/delete_webhook", methods=["GET"])
def delete_webhook():
    """[+] حذف Webhook الحالي"""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook",
            timeout=10
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            _webhook_status["is_set"] = False
            return jsonify({"status": "success", "message": "Webhook deleted"}), 200
        else:
            return jsonify({"error": resp.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# [+] تهيئة Webhook عند بدء التطبيق
# ============================================================

# [+] محاولة تعيين Webhook عند تحميل الوحدة (مرة واحدة)
try:
    ensure_webhook()
except Exception as e:
    logger.error(f"[-] فشل تعيين Webhook عند البدء: {e}")

# ============================================================
# [+] تصدير التطبيق لـ Vercel
# ============================================================

app = flask_app
@flask_app.route("/api/health", methods=["GET"])
def health_check():
    """[+] نقطة للتحقق من صحة التطبيق وتعيين Webhook"""
    result = ensure_webhook()
    return jsonify({
        "status": "ok",
        "webhook_set": result,
        "webhook_url": WEBHOOK_URL,
        "message": "Webhook ensured" if result else "Webhook not set"
    }), 200