import os
import re
import sys
import time
import uuid
import socket
import psutil
import platform
import requests
import asyncio
import logging
import datetime
import subprocess
import traceback
from io import StringIO
from inspect import getfullargspec

import aiofiles
from aiohttp import web

import json
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import (
    FloodWait,
    InputUserDeactivated,
    PeerIdInvalid,
    UserIsBlocked,
    SessionPasswordNeeded,
    PhoneNumberInvalid,
    ApiIdInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    ChatAdminRequired, 
    UserNotParticipant, 
    ChatWriteForbidden
)

# -----------------------------------------------------------------------------
# 1. إعدادات التكوين
# -----------------------------------------------------------------------------

BOT_TOKEN = "8052900952:AAEvZKao98ibPDlUqxBVcj6In1YOa4cbW18"
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
LOG_CHANNEL = -1003091756917
MUST_JOIN = "iIl337"
AUTH_USERS = [6689435577]
BROADCAST_AS_COPY = False
FORCE_SUBS = True
PORT = "8080"

# -----------------------------------------------------------------------------
# 2. إعدادات التسجيل
# -----------------------------------------------------------------------------

def remove_if_exists(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

remove_if_exists("logs.txt")
remove_if_exists("unknown_errors.txt")
remove_if_exists("my_account.session")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

LOGS = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 3. التخزين في الذاكرة (بدون قاعدة بيانات)
# -----------------------------------------------------------------------------

# تخزين بيانات المستخدمين في الذاكرة
user_sessions = {}
user_data = {}

class MemoryStorage:
    """تخزين بسيط في الذاكرة بدلاً من قاعدة البيانات"""
    
    @staticmethod
    async def add_user(user_id):
        if user_id not in user_data:
            user_data[user_id] = {
                "id": user_id,
                "join_date": datetime.date.today().isoformat(),
                "notif": True,
                "session": "",
                "login": False,
                "ban_status": {
                    "is_banned": False,
                    "ban_duration": 0,
                    "banned_on": datetime.date.max.isoformat(),
                    "ban_reason": "",
                },
                "api": "",
                "hash": ""
            }

    @staticmethod
    async def is_user_exist(user_id):
        return user_id in user_data

    @staticmethod
    async def total_users_count():
        return len(user_data)

    @staticmethod
    async def get_all_users():
        return list(user_data.values())

    @staticmethod
    async def delete_user(user_id):
        if user_id in user_data:
            del user_data[user_id]
        if user_id in user_sessions:
            del user_sessions[user_id]

    @staticmethod
    async def remove_ban(user_id):
        if user_id in user_data:
            user_data[user_id]["ban_status"] = {
                "is_banned": False,
                "ban_duration": 0,
                "banned_on": datetime.date.max.isoformat(),
                "ban_reason": "",
            }

    @staticmethod
    async def ban_user(user_id, ban_duration, ban_reason):
        if user_id in user_data:
            user_data[user_id]["ban_status"] = {
                "is_banned": True,
                "ban_duration": ban_duration,
                "banned_on": datetime.date.today().isoformat(),
                "ban_reason": ban_reason,
            }

    @staticmethod
    async def get_ban_status(user_id):
        if user_id in user_data:
            return user_data[user_id].get("ban_status", {
                "is_banned": False,
                "ban_duration": 0,
                "banned_on": datetime.date.max.isoformat(),
                "ban_reason": "",
            })
        return {
            "is_banned": False,
            "ban_duration": 0,
            "banned_on": datetime.date.max.isoformat(),
            "ban_reason": "",
        }

    @staticmethod
    async def get_all_banned_users():
        return [user for user in user_data.values() if user.get("ban_status", {}).get("is_banned")]

    @staticmethod
    async def set_notif(user_id, notif):
        if user_id in user_data:
            user_data[user_id]["notif"] = notif

    @staticmethod
    async def get_notif(user_id):
        if user_id in user_data:
            return user_data[user_id].get("notif", False)
        return False

    @staticmethod
    async def get_all_notif_user():
        return [user for user in user_data.values() if user.get("notif")]

    @staticmethod
    async def total_notif_users_count():
        return len([user for user in user_data.values() if user.get("notif")])

    @staticmethod
    async def set_session(user_id, session):
        if user_id in user_data:
            user_data[user_id]["session"] = session
        user_sessions[user_id] = session

    @staticmethod
    async def get_session(user_id):
        return user_sessions.get(user_id)

    @staticmethod
    async def set_api(user_id, api):
        if user_id in user_data:
            user_data[user_id]["api"] = api

    @staticmethod
    async def get_api(user_id):
        if user_id in user_data:
            return user_data[user_id].get("api")
        return None

    @staticmethod
    async def set_hash(user_id, hash):
        if user_id in user_data:
            user_data[user_id]["hash"] = hash

    @staticmethod
    async def get_hash(user_id):
        if user_id in user_data:
            return user_data[user_id].get("hash")
        return None

    @staticmethod
    async def set_login(user_id, login):
        if user_id in user_data:
            user_data[user_id]["login"] = login

    @staticmethod
    async def get_login(user_id):
        if user_id in user_data:
            return user_data[user_id].get("login", False)
        return False

# استخدام التخزين في الذاكرة
db = MemoryStorage()

# -----------------------------------------------------------------------------
# 4. نسخة البوت
# -----------------------------------------------------------------------------

bot = Client(
    "memadder",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# -----------------------------------------------------------------------------
# 5. وظائف مساعدة
# -----------------------------------------------------------------------------

async def aexec(code, client, message):
    exec(
        "async def __aexec(client, message): "
        + "".join(f"\n {a}" for a in code.split("\n"))
    )
    return await locals()["__aexec"](client, message)

async def edit_or_reply(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user.is_self else msg.reply
    spec = getfullargspec(func.__wrapped__).args
    await func(**{k: v for k, v in kwargs.items() if k in spec})

def if_url(url):
    regex = re.compile(
        r"^(?:http|ftp)s?://"
        r"t.me|"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$", 
        re.IGNORECASE
    )
    
    if re.match(regex, url) is not None:
        if "t.me" in url:
            xu = url.split("t.me/")[1]
            return f"@{xu}"
    elif "@" in url:
        return url
    return url

async def is_cancel(msg: Message, text: str):
    cancel_commands = ["/cancel", "/login", "/start", "/restart", "/help", "/memadd", "/status"]
    if any(text.startswith(cmd) for cmd in cancel_commands):
        await msg.reply("تم إلغاء العملية.")
        return True
    return False

async def send_animation(message, texts, delay=0.3):
    """إرسال رسوم متحركة للنصوص"""
    msg = await message.reply_text(texts[0])
    for text in texts[1:]:
        await asyncio.sleep(delay)
        await msg.edit_text(text)
    return msg

async def edit_nrbots(message):
    texts = [
        "**❤️.... نورا بوتس ....❤️**",
        "**.❤️... نورا بوتس ...❤️.**",
        "**..❤️.. نورا بوتس ..❤️..**",
        "**...❤️. نورا بوتس .❤️...**",
        "**....❤️ نورا بوتس ❤️....**"
    ]
    return await send_animation(message, texts)

async def edit_starting(message):
    texts = [
        "**❤️.... بدء تشغيل العميل ....❤️**",
        "**.❤️... بدء تشغيل العميل ...❤️.**",
        "**..❤️.. بدء تشغيل العميل ..❤️..**",
        "**...❤️. بدء تشغيل العميل .❤️...**",
        "**....❤️ بدء تشغيل العميل ❤️....**"
    ]
    return await send_animation(message, texts)

async def edit_initial(message):
    texts = [
        "**❤️........❤️**",
        "**.❤️......❤️.**",
        "**..❤️....❤️..**",
        "**...❤️..❤️...**",
        "**....❤️❤️....**",
        "🎊"
    ]
    return await send_animation(message, texts, 0.3)

async def edit_active(message):
    texts = [
        "**❤️.... بدء إضافة الأعضاء النشطين ....❤️**",
        "**.❤️... بدء إضافة الأعضاء النشطين ...❤️.**",
        "**..❤️.. بدء إضافة الأعضاء النشطين ..❤️..**",
        "**...❤️. بدء إضافة الأعضاء النشطين .❤️...**",
        "**....❤️ بدء إضافة الأعضاء النشطين ❤️....**"
    ]
    return await send_animation(message, texts)

async def edit_mixed(message):
    texts = [
        "**❤️.... بدء إضافة الأعضاء المختلطين ....❤️**",
        "**.❤️... بدء إضافة الأعضاء المختلطين ...❤️.**",
        "**..❤️.. بدء إضافة الأعضاء المختلطين ..❤️..**",
        "**...❤️. بدء إضافة الأعضاء المختلطين .❤️...**",
        "**....❤️ بدء إضافة الأعضاء المختلطين ❤️....**"
    ]
    return await send_animation(message, texts)

def create_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ انضم لقناة التحديثات ✨", url="https://t.me/iIl337")],
        [InlineKeyboardButton("✨ انضم لمجموعة الدعم ✨", url="https://t.me/NrBotsupport")]
    ])

async def get_bot_username():
    me = await bot.get_me()
    return me.username

async def get_bot_id():
    me = await bot.get_me()
    return me.id

START_TIME = datetime.datetime.utcnow()

TIME_DURATION_UNITS = (
    ("أسبوع", 60 * 60 * 24 * 7),
    ("يوم", 60 * 60 * 24),
    ("ساعة", 60 * 60),
    ("دقيقة", 60),
    ("ثانية", 1)
)

async def human_time_duration(seconds):
    if seconds == 0:
        return "∞"
    parts = []
    for unit, div in TIME_DURATION_UNITS:
        amount, seconds = divmod(int(seconds), div)
        if amount > 0:
            parts.append(f"{amount} {unit}")
    return ", ".join(parts)

START = """
مرحباً بك يا {}! 👋

أنا **بوت نقل الأعضاء** الذكي 🤖
يمكنني مساعدتك في نقل الأعضاء بين المجموعات والقنوات بسهولة وسرعة.

**المميزات:**
✅ نقل الأعضاء النشطين
✅ نقل الأعضاء المختلطين  
✅ واجهة عربية كاملة
✅ حماية متقدمة للحسابات

اختر أحد الخيارات أدناه للبدء:
"""

HELP = """
**🎯 أوامر البوت المتاحة:**

🔐 **/login** - تسجيل الدخول إلى حسابك
👥 **/memadd** - بدء عملية نقل الأعضاء  
📊 **/status** - التحقق من حالة التسجيل
🏓 **/ping** - فحص سرعة استجابة البوت

**📖 طريقة الاستخدام:**
1. أولاً قم بتسجيل الدخول باستخدام /login
2. ثم استخدم /memadd لبدء النقل
3. اتبع التعليمات خطوة بخطوة

**⚠️ ملاحظات مهمة:**
- استخدم حساباً وهمياً وليس حسابك الرئيسي
- احتفظ ببيانات API الخاصة بك في مكان آمن
- اتبع التعليمات بدقة لتجنب المشاكل
"""

START_BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("📚 المساعدة", callback_data="help"),
     InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
    [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd"),
     InlineKeyboardButton("📊 الحالة", callback_data="status")],
    [InlineKeyboardButton("🌐 قناة البوت", url="https://t.me/iIl337")]
])

HELP_BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏠 الرئيسية", callback_data="home"),
     InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
    [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd"),
     InlineKeyboardButton("❌ إغلاق", callback_data="close")]
])

def humanbytes(size):
    """تحويل البايتات إلى صيغة قابلة للقراءة"""
    if not size:
        return ""
    power = 2 ** 10
    raised_to_pow = 0
    dict_power_n = {0: "", 1: "كيلو", 2: "ميجا", 3: "جيجا", 4: "تيرا"}

    while size > power:
        size /= power
        raised_to_pow += 1
    return f"{round(size, 2)} {dict_power_n[raised_to_pow]}بايت"

async def check_subscription(user_id):
    """التحقق من اشتراك المستخدم في القناة"""
    if not FORCE_SUBS:
        return True
        
    try:
        user = await bot.get_chat_member(MUST_JOIN, user_id)
        return user.status not in ["kicked", "left"]
    except Exception:
        return False

async def force_subscribe(message):
    """إظهار رسالة الاشتراك الإجباري"""
    if not FORCE_SUBS:
        return True
        
    if not await check_subscription(message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 انضم للقناة", url=f"https://t.me/{MUST_JOIN}")],
            [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
        ])
        await message.reply_text(
            f"⚠️ **يجب الاشتراك في القناة أولاً**\n\n"
            f"اشترك هنا: https://t.me/{MUST_JOIN}\n\n"
            "بعد الاشتراك، اضغط على الزر أدناه للتحقق",
            reply_markup=keyboard
        )
        return False
    return True

# -----------------------------------------------------------------------------
# 6. الأوامر الرئيسية
# -----------------------------------------------------------------------------

@bot.on_message(filters.private & filters.command("start"))
async def start_command(client, message):
    await db.add_user(message.from_user.id)
    
    if not await force_subscribe(message):
        return
        
    await message.reply_text(
        text=START.format(message.from_user.mention),
        disable_web_page_preview=True,
        reply_markup=START_BUTTONS
    )

@bot.on_message(filters.private & filters.command("help"))
async def help_command(client, message):
    if not await force_subscribe(message):
        return
        
    await message.reply_text(
        text=HELP,
        disable_web_page_preview=True,
        reply_markup=HELP_BUTTONS
    )

@bot.on_message(filters.command("ping"))
async def ping_command(client, message):
    start = time.time()
    m_reply = await message.reply_text("جاري فحص السرعة...")
    delta_ping = time.time() - start
    current_time = datetime.datetime.utcnow()
    uptime_sec = (current_time - START_TIME).total_seconds()
    uptime = await human_time_duration(int(uptime_sec))
    
    await m_reply.edit_text(
        f"🏓 **السرعة:** **{delta_ping * 1000:.3f} مللي ثانية** \n"
        f"⚡️ **مدة التشغيل:** **{uptime}**\n\n"
        f"💖 **@iIl337**"
    )

# -----------------------------------------------------------------------------
# 7. أوامر التسجيل وإضافة الأعضاء
# -----------------------------------------------------------------------------

PHONE_NUMBER_TEXT = (
    "أرسل الآن رقم هاتف حساب Telegram الخاص بك بالتنسيق الدولي.\n"
    "تضمين رمز البلد. مثال: **+966501234567** \n\n"
    "اضغط /cancel لإلغاء المهمة."
)

API_TEXT = (
    "أرسل الـ API ID الخاص بك...\n\n"
    "إذا كنت لا تعرف من أين تحصل عليه:\n"
    "1- اذهب إلى موقع Telegram هذا: https://my.telegram.org\n"
    "2- سجل الدخول بحسابك\n"
    "3- انسخ الـ API ID وأرسله هنا"
)

HASH_TEXT = (
    "أرسل الـ API Hash الخاص بك...\n\n"
    "إذا كنت لا تعرف من أين تحصل عليه:\n"
    "1- اذهب إلى موقع Telegram هذا: https://my.telegram.org\n"
    "2- سجل الدخول بحسابك\n"
    "3- انسخ الـ API Hash وأرسله هنا"
)

@bot.on_message(filters.private & filters.command("login"))
async def login_command(client, message):
    if not await force_subscribe(message):
        return
        
    await edit_nrbots(message)
    await asyncio.sleep(0.4)
    
    await message.reply(
        f"مرحباً {message.from_user.mention}!\n\n"
        "لمزيد من الأمان لحسابك، يجب أن تزودني بـ API ID و API Hash لتسجيل الدخول إلى حسابك\n\n"
        "⚠️ **يرجى تسجيل الدخول إلى حساب وهمي، ولا تستخدم حسابك الحقيقي** ⚠️\n\n"
        "شاهد طريقة الحصول على API ID و API Hash:\n"
        "https://youtu.be/NsbhYHz7K_w"
    )
    await asyncio.sleep(2)
    
    chat = message.chat
    
    # طلب API ID
    api_msg = await bot.ask(chat.id, API_TEXT)
    if await is_cancel(message, api_msg.text):
        return
        
    try:
        api_id = int(api_msg.text)
    except ValueError:
        await message.reply("`API ID` غير صالح.\nاضغط على /login لتسجيل مرة أخرى.")
        return
    
    # طلب API Hash
    hash_msg = await bot.ask(chat.id, HASH_TEXT)
    if await is_cancel(message, hash_msg.text):
        return
        
    if len(hash_msg.text) < 30:
        await message.reply("`API Hash` غير صالح.\nاضغط على /login لتسجيل مرة أخرى")
        return
    api_hash = hash_msg.text
    
    # طلب رقم الهاتف
    while True:
        number_msg = await bot.ask(chat.id, PHONE_NUMBER_TEXT)
        if not number_msg.text:
            continue
        if await is_cancel(message, number_msg.text):
            return
            
        phone = number_msg.text
        confirm_msg = await bot.ask(
            chat.id, 
            f'هل الرقم "{phone}" صحيح؟ (y/n):\n\n'
            f'أرسل: `y` (إذا كان الرقم صحيح)\n'
            f'أرسل: `n` (إذا كان الرقم خطأ)'
        )
        if await is_cancel(message, confirm_msg.text):
            return
            
        if confirm_msg.text.lower() == "y":
            break
    
    # إنشاء العميل وتسجيل الدخول
    try:
        user_client = Client(
            f"{chat.id}_account", 
            api_id=api_id, 
            api_hash=api_hash, 
            in_memory=True
        )
        
        await user_client.connect()
        code = await user_client.send_code(phone)
        
        # طلب رمز OTP
        otp_msg = """
تم إرسال رمز مكون من 5 أرقام إلى رقم هاتفك.
الرجاء إرسال الرمز بالتنسيق: 1 2 3 4 5 (مسافة بين كل رقم!)

إذا لم يصلك الرمز، حاول إعادة تشغيل البوت واستخدام الأمر /start مرة أخرى.
اضغط /cancel للإلغاء.
"""
        otp_msg_obj = await bot.ask(chat.id, otp_msg, timeout=300)
        if await is_cancel(message, otp_msg_obj.text):
            return
            
        otp_code = otp_msg_obj.text
        
        try:
            await user_client.sign_in(phone, code.phone_code_hash, phone_code=' '.join(otp_code.split()))
        except SessionPasswordNeeded:
            # التحقق بخطوتين
            two_step_msg = await bot.ask(
                chat.id, 
                "حسابك محمي بالتحقق بخطوتين.\nأرسل رمز التحقق بخطوتين.\n\nاضغط /cancel للإلغاء.",
                timeout=300
            )
            if await is_cancel(message, two_step_msg.text):
                return
                
            await user_client.check_password(two_step_msg.text)
        
        # تسجيل الدخول ناجح
        session_string = await user_client.export_session_string()
        await db.set_session(chat.id, session_string)
        await db.set_api(chat.id, api_id)
        await db.set_hash(chat.id, api_hash)
        await db.set_login(chat.id, True)
        
        await user_client.disconnect()
        
        await message.reply(
            "✅ **تم التسجيل بنجاح!**\n\n"
            "يمكنك الآن استخدام الأمر /memadd لبدء نقل الأعضاء",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd")],
                [InlineKeyboardButton("📊 حالة الحساب", callback_data="status")]
            ])
        )
        
    except FloodWait as e:
        await message.reply(f"حسابك لديه انتظار لمدة {e.value} ثانية. يرجى المحاولة بعد {e.value} ثانية")
    except (ApiIdInvalid, PhoneNumberInvalid) as e:
        await message.reply("بيانات التسجيل غير صالحة. يرجى التحقق والمحاولة مرة أخرى.")
    except (PhoneCodeInvalid, PhoneCodeExpired) as e:
        await message.reply("الرمز غير صالح أو منتهي الصلاحية. يرجى المحاولة مرة أخرى.")
    except Exception as e:
        await message.reply(f"**خطأ:** `{str(e)}`")

@bot.on_message(filters.private & filters.command("status"))
async def status_command(client, message):
    if not await force_subscribe(message):
        return
        
    user_id = message.from_user.id
    session = await db.get_session(user_id)
    
    if not session:
        await message.reply(
            "⚠️ **لم يتم تسجيل الدخول بعد**\n\n"
            'يجب تسجيل الدخول لاستخدام جميع ميزات البوت',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
                [InlineKeyboardButton("📚 المساعدة", callback_data="help")]
            ])
        )
        return
    
    try:
        api_id = await db.get_api(user_id) or API_ID
        api_hash = await db.get_hash(user_id) or API_HASH
        
        user_client = Client(f"{user_id}_status", session_string=session, api_id=api_id, api_hash=api_hash, in_memory=True)
        await user_client.start()
        user_info = await user_client.get_me()
        await user_client.stop()
        
        status_text = f"""
**📊 معلومات الحساب المسجل**

**الاسم:** {user_info.first_name}
**اسم المستخدم:** @{user_info.username}
**الرقم التعريفي:** {user_info.id}
**حالة التسجيل:** ✅ نشط

**خيارات الإدارة:**
"""
        await message.reply(
            status_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔓 تسجيل الخروج", callback_data="logout_confirm")],
                [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
            ])
        )
        
    except Exception as e:
        await message.reply(
            "❌ **خطأ في جلسة التسجيل**\n\n"
            "يبدو أن جلسة التسجيل لم تعد صالحة. يرجى تسجيل الدخول مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")]
            ])
        )

# -----------------------------------------------------------------------------
# 8. معالجات الاستدعاء (Callback Handlers)
# -----------------------------------------------------------------------------

@bot.on_callback_query(filters.regex("home"))
async def home_callback(client, callback_query):
    await callback_query.message.edit_text(
        text=START.format(callback_query.from_user.mention),
        disable_web_page_preview=True,
        reply_markup=START_BUTTONS
    )

@bot.on_callback_query(filters.regex("help"))
async def help_callback(client, callback_query):
    await callback_query.message.edit_text(
        text=HELP,
        disable_web_page_preview=True,
        reply_markup=HELP_BUTTONS
    )

@bot.on_callback_query(filters.regex("close"))
async def close_callback(client, callback_query):
    await callback_query.message.delete()

@bot.on_callback_query(filters.regex("login"))
async def login_callback(client, callback_query):
    await callback_query.message.edit_text(
        "🔐 **تسجيل الدخول**\n\n"
        "سيتم بدء عملية تسجيل الدخول إلى حسابك.\n\n"
        "اضغط على الزر أدناه للمتابعة:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 بدء التسجيل", callback_data="start_login")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
        ])
    )

@bot.on_callback_query(filters.regex("start_login"))
async def start_login_callback(client, callback_query):
    await callback_query.message.delete()
    await login_command(client, callback_query.message)

@bot.on_callback_query(filters.regex("memadd"))
async def memadd_callback(client, callback_query):
    await callback_query.message.edit_text(
        "👥 **نقل الأعضاء**\n\n"
        "سيتم بدء عملية نقل الأعضاء بين المجموعات.\n\n"
        "يجب أن تكون مسجلاً الدخول أولاً لاستخدام هذه الميزة.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
            [InlineKeyboardButton("📊 حالة التسجيل", callback_data="status")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
        ])
    )

@bot.on_callback_query(filters.regex("status"))
async def status_callback(client, callback_query):
    await callback_query.message.delete()
    await status_command(client, callback_query.message)

@bot.on_callback_query(filters.regex("logout_confirm"))
async def logout_confirm_callback(client, callback_query):
    await callback_query.message.edit_text(
        "⚠️ **تأكيد تسجيل الخروج**\n\n"
        "هل أنت متأكد من أنك تريد تسجيل الخروج؟\n"
        "سيتم مسح جميع بيانات تسجيل الدخول.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم، سجل الخروج", callback_data="confirm_logout")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="status")]
        ])
    )

@bot.on_callback_query(filters.regex("confirm_logout"))
async def confirm_logout_callback(client, callback_query):
    user_id = callback_query.from_user.id
    await db.set_session(user_id, "")
    await db.set_login(user_id, False)
    
    await callback_query.message.edit_text(
        "✅ **تم تسجيل الخروج بنجاح**\n\n"
        "تم مسح بيانات تسجيل الدخول بنجاح.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
        ])
    )

@bot.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client, callback_query):
    user_id = callback_query.from_user.id
    if await check_subscription(user_id):
        await callback_query.message.edit_text(
            "✅ **تم الاشتراك بنجاح**\n\n"
            "يمكنك الآن استخدام البوت.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 ابدأ الاستخدام", callback_data="home")]
            ])
        )
    else:
        await callback_query.message.edit_text(
            "❌ **لم تشترك بعد**\n\n"
            "يجب الاشتراك في القناة أولاً.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 انضم للقناة", url=f"https://t.me/{MUST_JOIN}")],
                [InlineKeyboardButton("🔄 تحقق مرة أخرى", callback_data="check_sub")]
            ])
        )

# -----------------------------------------------------------------------------
# 9. التشغيل الرئيسي
# -----------------------------------------------------------------------------

async def main():
    try:
        print("جاري بدء تشغيل البوت...")
        LOGS.info("جاري بدء تشغيل البوت...")

        await bot.start()
        
        # إرسال رسالة بدء التشغيل إلى قناة السجلات
        try:
            bot_info = await bot.get_me()
            await bot.send_message(
                LOG_CHANNEL,
                f"✅ **تم بدء تشغيل البوت بنجاح**\n\n"
                f"**اسم البوت:** @{bot_info.username}\n"
                f"**وقت البدء:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"**الإصدار:** 2.0 (بدون قاعدة بيانات)"
            )
        except Exception as e:
            print(f"خطأ في إرسال رسالة البدء: {e}")

        print("✅ تم بدء تشغيل البوت بنجاح!")
        await idle()
        
    except Exception as e:
        print(f"خطأ في التشغيل: {e}")
        LOGS.error(e)

if __name__ == "__main__":
    bot.run(main())
