# api/webhook.py
# [+] نقطة دخول فيرسل - معاد هيكلته بالكامل للتوافق مع ASGI

import sys
import os
import json
import logging
import asyncio
import requests
from typing import Dict, Any

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

# [+] متغيرات عامة للتحكم في تهيئة الويب هوك
_webhook_set = False

# ============================================================
# [+] تهيئة التطبيق (يتم استدعاؤها مرة واحدة فقط)
# ============================================================

def init_application() -> Application:
    """[+] تهيئة تطبيق البوت مع جميع المعالجات"""
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # [+] أوامر نصية
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("admin", admin.admin_panel_command))
    app.add_handler(CommandHandler("add_points", admin.add_points_command))
    app.add_handler(CommandHandler("remove_points", admin.remove_points_command))
    app.add_handler(CommandHandler("create_gift", admin.create_gift_command))
    app.add_handler(CommandHandler("ban", admin.ban_command))
    app.add_handler(CommandHandler("unban", admin.unban_command))
    app.add_handler(CommandHandler("banned_list", admin.banned_list_command))
    
    # [+] معالج محادثة الأدمن
    app.add_handler(admin.get_admin_conversation_handler())
    
    # [+] استعلامات رد الاتصال
    app.add_handler(CallbackQueryHandler(extract_button, pattern="^extract$"))
    app.add_handler(CallbackQueryHandler(cancel_extract, pattern="^cancel_extract$"))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_image))
    app.add_handler(CallbackQueryHandler(other_callbacks, pattern="^(?!extract$|cancel_extract$|admin_).*$"))
    
    # [+] معالج الأخطاء العام
    app.add_error_handler(error_handler)
    
    # [+] تهيئة قاعدة البيانات (مرة واحدة)
    db.init_db()
    
    logger.info("[+] تم تهيئة تطبيق البوت بنجاح")
    return app

# ============================================================
# [+] تعيين الويب هوك بأمان مع منع التكرار
# ============================================================

def set_webhook_safe() -> bool:
    """[+] تعيين الويب هوك مع التحقق من عدم التكرار"""
    global _webhook_set
    
    if _webhook_set:
        logger.debug("[~] تم تعيين الويب هوك مسبقاً، تخطي")
        return True
    
    webhook_url = "https://member-serv.vercel.app/api/webhook"
    api_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/setWebhook"
    
    try:
        # [+] التحقق من الويب هوك الحالي أولاً
        check_url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getWebhookInfo"
        check_resp = requests.get(check_url, timeout=10)
        if check_resp.status_code == 200:
            info = check_resp.json()
            if info.get("ok") and info.get("result", {}).get("url") == webhook_url:
                logger.info("[=] الويب هوك مُعيّن بالفعل بشكل صحيح")
                _webhook_set = True
                return True
        
        # [+] تعيين الويب هوك
        resp = requests.post(api_url, json={"url": webhook_url}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                logger.info(f"[+] تم تعيين الويب هوك بنجاح إلى {webhook_url}")
                _webhook_set = True
                return True
            else:
                logger.error(f"[-] فشل تعيين الويب هوك: {data.get('description')}")
                return False
        else:
            logger.error(f"[-] HTTP {resp.status_code} من واجهة برمجة تطبيقات تيليجرام")
            return False
    except Exception as e:
        logger.error(f"[-] خطأ في تعيين الويب هوك: {e}")
        return False

# ============================================================
# [+] نقطة الدخول من فيرسل - متوافقة مع ASGI
# ============================================================

# [+] يتم إنشاء التطبيق مرة واحدة عند تحميل الوحدة
_app_instance = None

def get_app() -> Application:
    """[+] الحصول على نسخة التطبيق (تهيئة كسولة)"""
    global _app_instance
    if _app_instance is None:
        _app_instance = init_application()
    return _app_instance

async def app(scope: Dict[str, Any], receive: Any, send: Any) -> None:
    """[+] نقطة دخول ASGI الرئيسية المتوافقة مع فيرسل"""
    
    # [+] معالجة طلبات HTTP
    if scope["type"] == "http":
        # [+] الحصول على الطلب
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
        
        # [+] تحليل المسار والطريقة
        path = scope.get("path", "/")
        method = scope.get("method", "GET")
        
        # [+] معالجة طلب POST من تيليجرام
        if method == "POST" and path == "/api/webhook":
            try:
                # [+] تعيين الويب هوك بأمان (مرة واحدة)
                set_webhook_safe()
                
                # [+] الحصول على التطبيق المُهيأ
                app_instance = get_app()
                
                # [+] تحليل نص الطلب
                body_text = body.decode("utf-8")
                update_data = json.loads(body_text)
                logger.info(f"[+] تحديث وارد: {update_data.get('update_id', 'غير معروف')}")
                
                # [+] معالجة التحديث
                update = Update.de_json(update_data, app_instance.bot)
                await app_instance.process_update(update)
                
                # [+] إرسال استجابة نجاح
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"ok": true}',
                })
                
            except json.JSONDecodeError as e:
                logger.error(f"[-] خطأ في تحليل JSON: {e}")
                await send({
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Invalid JSON"}',
                })
                
            except Exception as e:
                logger.error(f"[-] خطأ غير متوقع: {e}", exc_info=True)
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Internal server error"}',
                })
        
        # [+] معالجة طلبات GET للتحقق من الصحة
        else:
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"status": "ok", "message": "UFOQ Bot is running"}',
            })
    
    # [+] تجاهل الأنواع الأخرى من النطاقات
    else:
        pass

# ============================================================
# [+] تصدير المتغير المطلوب من فيرسل
# ============================================================

# [+] هذا هو المتغير الذي يبحث عنه فيرسل
# [+] فيرسل يتوقع 'app' كتطبيق ASGI

# [+] للتوافق مع الإصدارات القديمة، نحتفظ بـ 'webhook' أيضاً
webhook = app