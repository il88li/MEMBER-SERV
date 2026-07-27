# api/webhook.py
# [+] أبسط نقطة دخول لـ Vercel مع Flask

import sys
import os
import json
import logging
import asyncio
import requests
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
# [+] تهيئة البوت (مرة واحدة)
# ============================================================

app_bot = None

def get_bot_app():
    global app_bot
    if app_bot is None:
        app_bot = Application.builder().token(config.BOT_TOKEN).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CommandHandler("cancel", cancel_command))
        app_bot.add_handler(CommandHandler("admin", admin.admin_panel_command))
        app_bot.add_handler(CommandHandler("add_points", admin.add_points_command))
        app_bot.add_handler(CommandHandler("remove_points", admin.remove_points_command))
        app_bot.add_handler(CommandHandler("create_gift", admin.create_gift_command))
        app_bot.add_handler(CommandHandler("ban", admin.ban_command))
        app_bot.add_handler(CommandHandler("unban", admin.unban_command))
        app_bot.add_handler(CommandHandler("banned_list", admin.banned_list_command))
        app_bot.add_handler(admin.get_admin_conversation_handler())
        app_bot.add_handler(CallbackQueryHandler(extract_button, pattern="^extract$"))
        app_bot.add_handler(CallbackQueryHandler(cancel_extract, pattern="^cancel_extract$"))
        app_bot.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_image))
        app_bot.add_handler(CallbackQueryHandler(other_callbacks, pattern="^(?!extract$|cancel_extract$|admin_).*$"))
        app_bot.add_error_handler(error_handler)
        db.init_db()
        logger.info("[+] تم تهيئة البوت")
    return app_bot

# ============================================================
# [+] تطبيق Flask
# ============================================================

flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "UFOQ Bot is running"}), 200

@flask_app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON"}), 400
        
        logger.info(f"[+] تحديث: {data.get('update_id')}")
        bot = get_bot_app()
        update = Update.de_json(data, bot.bot)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.process_update(update))
        loop.close()
        
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"[-] خطأ: {e}")
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/set_webhook", methods=["GET"])
def set_webhook():
    webhook_url = "https://ufoqai.vercel.app/api/webhook"
    api_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook"
    
    try:
        # [+] حذف القديم
        requests.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteWebhook", timeout=5)
        # [+] تعيين الجديد
        resp = requests.post(api_url, json={"url": webhook_url}, timeout=10)
        return jsonify({
            "status": "success" if resp.json().get("ok") else "error",
            "response": resp.json()
        }), 200 if resp.json().get("ok") else 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@flask_app.route("/api/webhook_info", methods=["GET"])
def info():
    resp = requests.get(f"https://api.telegram.org/bot{config.BOT_TOKEN}/getWebhookInfo", timeout=10)
    return jsonify(resp.json()), 200

# ============================================================
# [+] تصدير لـ Vercel
# ============================================================

app = flask_app