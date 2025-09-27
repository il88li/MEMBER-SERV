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
    FloodWait as FloodWait1,
    InputUserDeactivated,
    PeerIdInvalid,
    UserIsBlocked,
    SessionPasswordNeeded as SessionPasswordNeeded1,
    PhoneNumberInvalid as PhoneNumberInvalid1,
    ApiIdInvalid as ApiIdInvalid1,
    PhoneCodeInvalid as PhoneCodeInvalid1,
    PhoneCodeExpired as PhoneCodeExpired1,
    ChatAdminRequired, UserNotParticipant, ChatWriteForbidden
)
from pyromod import listen
from pyromod.helpers import ikb


# -----------------------------------------------------------------------------
# 1. إعدادات التكوين
# -----------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8052900952:AAEvZKao98ibPDlUqxBVcj6In1YOa4cbW18")
API_ID = int(os.environ.get("API_ID", "23656977"))
API_HASH = os.environ.get("API_HASH", "49d3f43531a92b3f5bc403766313ca1e")
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003091756917"))
MUST_JOIN = os.environ.get("MUST_JOIN", "iIl337")
AUTH_USERS = set(int(x) for x in os.environ.get("AUTH_USERS", "6689435577").split())
DB_URL = os.environ.get("DB_URL", "mongodb+srv://nora:nora@nora.f0ea0ix.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.environ.get("DB_NAME", "memadder")
BROADCAST_AS_COPY = bool(os.environ.get("BROADCAST_AS_COPY", False))
FORCE_SUBS = bool(os.environ.get("FORCE_SUBSCRIBE", False))
PORT = os.environ.get("PORT", "8080")


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
  filename=f"logs.txt",
  level=logging.INFO,
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

LOGS = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 3. فئة قاعدة البيانات
# -----------------------------------------------------------------------------

class Database:
    def __init__(self, users_file="users.json", config_file="config.json"):
        self.users_file = users_file
        self.config_file = config_file
        self._initialize_files()

    def _initialize_files(self):
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w') as f:
                json.dump({}, f)
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump({}, f)

    async def _read_data(self, file_path):
        async with aiofiles.open(file_path, mode='r') as f:
            content = await f.read()
            return json.loads(content)

    async def _write_data(self, file_path, data):
        async with aiofiles.open(file_path, mode='w') as f:
            await f.write(json.dumps(data, indent=4))

    async def _get_users_data(self):
        return await self._read_data(self.users_file)

    async def _set_users_data(self, data):
        await self._write_data(self.users_file, data)

    async def _get_config_data(self):
        return await self._read_data(self.config_file)

    async def _set_config_data(self, data):
        await self._write_data(self.config_file, data)

    def new_user(self, id):
        return {
            "id": id,
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

    async def add_user(self, id):
        users = await self._get_users_data()
        if str(id) not in users:
            users[str(id)] = self.new_user(id)
            await self._set_users_data(users)

    async def is_user_exist(self, id):
        users = await self._get_users_data()
        return str(id) in users

    async def total_users_count(self):
        users = await self._get_users_data()
        return len(users)

    async def get_all_users(self):
        users = await self._get_users_data()
        return [user_data for user_data in users.values()]

    async def delete_user(self, user_id):
        users = await self._get_users_data()
        if str(user_id) in users:
            del users[str(user_id)]
            await self._set_users_data(users)

    async def remove_ban(self, id):
        users = await self._get_users_data()
        if str(id) in users:
            users[str(id)]["ban_status"] = {
                "is_banned": False,
                "ban_duration": 0,
                "banned_on": datetime.date.max.isoformat(),
                "ban_reason": "",
            }
            await self._set_users_data(users)

    async def ban_user(self, user_id, ban_duration, ban_reason):
        users = await self._get_users_data()
        if str(user_id) in users:
            users[str(user_id)]["ban_status"] = {
                "is_banned": True,
                "ban_duration": ban_duration,
                "banned_on": datetime.date.today().isoformat(),
                "ban_reason": ban_reason,
            }
            await self._set_users_data(users)

    async def get_ban_status(self, id):
        users = await self._get_users_data()
        user = users.get(str(id))
        if user:
            return user.get("ban_status", {
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

    async def get_all_banned_users(self):
        users = await self._get_users_data()
        return [user_data for user_data in users.values() if user_data.get("ban_status", {}).get("is_banned")]

    async def set_notif(self, id, notif):
        users = await self._get_users_data()
        if str(id) in users:
            users[str(id)]["notif"] = notif
            await self._set_users_data(users)

    async def get_notif(self, id):
        users = await self._get_users_data()
        user = users.get(str(id))
        return user.get("notif", False) if user else False

    async def get_all_notif_user(self):
        users = await self._get_users_data()
        return [user_data for user_data in users.values() if user_data.get("notif")]

    async def total_notif_users_count(self):
        users = await self._get_users_data()
        return len([user_data for user_data in users.values() if user_data.get("notif")])

    async def set_session(self, id, session):
        users = await self._get_users_data()
        if str(id) in users:
            users[str(id)]["session"] = session
            await self._set_users_data(users)

    async def get_session(self, id):
        users = await self._get_users_data()
        user = users.get(str(id))
        return user.get("session") if user else None

    async def set_api(self, id, api):
        users = await self._get_users_data()
        if str(id) in users:
            users[str(id)]["api"] = api
            await self._set_users_data(users)

    async def get_api(self, id):
        users = await self._get_users_data()
        user = users.get(str(id))
        return user.get("api") if user else None

    async def set_hash(self, id, hash):
        users = await self._get_users_data()
        if str(id) in users:
            users[str(id)]["hash"] = hash
            await self._set_users_data(users)

    async def get_hash(self, id):
        users = await self._get_users_data()
        user = users.get(str(id))
        return user.get("hash") if user else None

    async def set_login(self, id, login: bool):
        users = await self._get_users_data()
        if str(id) in users:
            users[str(id)]["login"] = login
            await self._set_users_data(users)

    async def get_login(self, id):
        users = await self._get_users_data()
        user = users.get(str(id))
        return user.get("login") if user else False

    async def set_fsub_channel(self, channel):
        config_data = await self._get_config_data()
        config_data["fsub_channel"] = channel
        await self._set_config_data(config_data)

    async def get_fsub_channel(self):
        config_data = await self._get_config_data()
        return config_data.get("fsub_channel")

    async def set_fsub(self, status: bool):
        config_data = await self._get_config_data()
        config_data["fsub"] = status
        await self._set_config_data(config_data)

    async def get_fsub(self):
        config_data = await self._get_config_data()
        return config_data.get("fsub")

    async def set_bcopy(self, status: bool):
        config_data = await self._get_config_data()
        config_data["bcopy"] = status
        await self._set_config_data(config_data)

    async def get_bcopy(self):
        config_data = await self._get_config_data()
        return config_data.get("bcopy")

db = Database()


# -----------------------------------------------------------------------------
# 4. نسخة البوت
# -----------------------------------------------------------------------------

bot = Client(
    "memadder",
    api_id = API_ID,
    api_hash = API_HASH,
    bot_token = BOT_TOKEN,
)


# -----------------------------------------------------------------------------
# 5. وظائف الويب
# -----------------------------------------------------------------------------

routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    bot_log_path = f"logs.txt"
    m_list = open(bot_log_path, "r").read()
    message_s = m_list.replace("\n","")
    return web.json_response(message_s)


async def web_server():
    web_app = web.Application(client_max_size=30000000000)
    web_app.add_routes(routes)
    return web_app


# -----------------------------------------------------------------------------
# 6. وظائف مساعدة
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
            r"(?:/?|[/?]\S+)$"
            , re.IGNORECASE)
    
    string = url
    x = re.match(regex, string) is not None 
    if x:
        if "t.me" in string:
            xu = string.split("t.me/")[1]
            return f"@{xu}"
    elif "@" in string:
        xu = string
        return xu

async def is_cancel(msg: Message, text: str):
    if text.startswith("/cancel"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    elif text.startswith("/login"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    elif text.startswith("/start"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    elif text.startswith("/restart"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    elif text.startswith("/help"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    elif text.startswith("/memadd"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    elif text.startswith("/status"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    elif text.startswith("/"):
        await msg.reply("تم إلغاء التسجيل.")
        return True
    return False

async def type_(text: str):
    text = text.lower()
    if text == "y":
        return True
    elif text == "n":
        return False
    else:
        return False

async def edit_nrbots(nr):
    await nr.edit_text("**❤️.... نورا بوتس ....❤️**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**.❤️... نورا بوتس ...❤️.**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**..❤️.. نورا بوتس ..❤️..**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**...❤️. نورا بوتس .❤️...**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**....❤️ نورا بوتس ❤️....**")
    await asyncio.sleep(0.5)

async def edit_starting(nr):
    await nr.edit_text("**❤️.... بدء تشغيل العميل ....❤️**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**.❤️... بدء تشغيل العميل ...❤️.**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**..❤️.. بدء تشغيل العميل ..❤️..**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**...❤️. بدء تشغيل العميل .❤️...**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**....❤️ بدء تشغيل العميل ❤️....**")
    await asyncio.sleep(0.5)

async def edit_ini(nr):
    await nr.edit_text("**❤️........❤️**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**.❤️......❤️.**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**..❤️....❤️..**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**...❤️..❤️...**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**....❤️❤️....**")
    await asyncio.sleep(0.3)
    await nr.edit_text("🎊")
    await asyncio.sleep(0.4)

async def edit_active(nr):
    await nr.edit_text("**❤️.... بدء إضافة الأعضاء النشطين ....❤️**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**.❤️... بدء إضافة الأعضاء النشطين ...❤️.**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**..❤️.. بدء إضافة الأعضاء النشطين ..❤️..**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**...❤️. بدء إضافة الأعضاء النشطين .❤️...**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**....❤️ بدء إضافة الأعضاء النشطين ❤️....**")
    await asyncio.sleep(0.5)

async def edit_mixed(nr):
    await nr.edit_text("**❤️.... بدء إضافة الأعضاء المختلطين ....❤️**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**.❤️... بدء إضافة الأعضاء المختلطين ...❤️.**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**..❤️.. بدء إضافة الأعضاء المختلطين ..❤️..**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**...❤️. بدء إضافة الأعضاء المختلطين .❤️...**")
    await asyncio.sleep(0.3)
    await nr.edit_text("**....❤️ بدء إضافة الأعضاء المختلطين ❤️....**")
    await asyncio.sleep(0.5)

keyboard = ikb([
        [("✨ انضم لقناة التحديثات ✨", "https://t.me/iIl337", "url")], 
        [("✨ انضم لمجموعة الدعم ✨", "https://t.me/NrBotsupport", "url")]
])

async def getme():
    data = await bot.get_me()
    BOT_USERNAME = data.username
    return str(BOT_USERNAME)

async def botid():
    data = await bot.get_me()
    BOT_ID = data.id
    return (BOT_ID)

START_TIME = datetime.datetime.utcnow()
START_TIME_ISO = START_TIME.replace(microsecond=0).isoformat()
TIME_DURATION_UNITS = (
    ("أسبوع", 60 * 60 * 24 * 7),
    ("يوم", 60 * 60 * 24),
    ("ساعة", 60 * 60),
    ("دقيقة", 60),
    ("ثانية", 1)
)
async def _human_time_duration(seconds):
    if seconds == 0:
        return "∞"
    parts = []
    for unit, div in TIME_DURATION_UNITS:
        amount, seconds = divmod(int(seconds), div)
        if amount > 0:
            parts.append("{} {}{}"
                         .format(amount, unit, "" if amount == 1 else ""))
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

START_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("📚 المساعدة", callback_data="help"),
         InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
        [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd"),
         InlineKeyboardButton("📊 الحالة", callback_data="status")],
        [InlineKeyboardButton("🌐 قناة البوت", url="https://t.me/iIl337")]
    ]
)

HELP_BUTTONS = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="home"),
         InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
        [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd"),
         InlineKeyboardButton("❌ إغلاق", callback_data="close")]
    ]
)

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
    return str(round(size, 2)) + " " + dict_power_n[raised_to_pow] + "بايت"

async def set_global_channel():
    global MUST_JOIN
    MUST_JOIN = await db.get_fsub_channel()
    
async def set_global_fsub():
    global FORCE_SUBS
    FORCE_SUBS = await db.get_fsub()

async def handle_user_status(client, msg):
    # وظيفة فارغة - يمكن تطويرها لاحقاً
    pass

async def eor(message, text, parse_mode="md"):
    if message.from_user.id:
        if message.reply_to_message:
            kk = message.reply_to_message.message_id
            return await message.reply_text(
                text, reply_to_message_id=kk, parse_mode=parse_mode
            )
        return await message.reply_text(text, parse_mode=parse_mode)
    return await message.edit(text, parse_mode=parse_mode)

def get_text(message: Message) -> [None, str]:
    """استخراج النص من الأوامر"""
    text_to_return = message.text
    if message.text is None:
        return None
    if " " in text_to_return:
        try:
            return message.text.split(None, 1)[1]
        except IndexError:
            return None
    else:
        return None


# -----------------------------------------------------------------------------
# 7. الأوامر ومعالجات الرسائل
# -----------------------------------------------------------------------------

@bot.on_message(filters.private & filters.command("start"))
async def start_pm(client: Client, message: Message):
    user_id = message.from_user.id
    await db.add_user(user_id)
    
    # التحقق من الاشتراك الإجباري
    if FORCE_SUBS:
        try:
            user = await bot.get_chat_member(MUST_JOIN, user_id)
            if user.status == "kicked":
                await message.reply_text("❌ تم حظرك من استخدام البوت")
                return
        except UserNotParticipant:
            invite_link = f"https://t.me/{MUST_JOIN}"
            await message.reply_text(
                f"⚠️ **يجب الاشتراك في القناة أولاً**\n\n"
                f"اشترك هنا: {invite_link}\n\n"
                "بعد الاشتراك، اضغط على /start مرة أخرى",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 انضم للقناة", url=invite_link)],
                    [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
                ])
            )
            return
    
    await message.reply_text(
        text=START.format(message.from_user.mention),
        disable_web_page_preview=True,
        reply_markup=START_BUTTONS
    )

@bot.on_message(filters.private & filters.command("help"))
async def help_pm(bot: Client, message: Message):
    await message.reply_text(
        text=HELP,
        disable_web_page_preview=True,
        reply_markup=HELP_BUTTONS
    )

@bot.on_message(filters.command("ping"))
async def ping_pong(client, message):       
    start = time.time()
    m_reply = await message.reply_text("جاري فحص السرعة...")
    delta_ping = time.time() - start
    current_time = datetime.datetime.utcnow()
    uptime_sec = (current_time - START_TIME).total_seconds()
    uptime = await _human_time_duration(int(uptime_sec))
    await m_reply.edit_text(
        f"🏓 **السرعة:**  **{delta_ping * 1000:.3f} مللي ثانية** \n"
        f"⚡️ **مدة التشغيل:** **{uptime}**\n\n"
        f"💖 ** @iIl337**"
    )

PHONE_NUMBER_TEXT = (
    "أرسل الآن رقم هاتف حساب Telegram الخاص بك بالتنسيق الدولي.  \n"
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
async def genStr(_, msg: Message):
    # التحقق من الاشتراك الإجباري
    if FORCE_SUBS:
        try:
            user = await bot.get_chat_member(MUST_JOIN, msg.from_user.id)
            if user.status == "kicked":
                await msg.reply_text("❌ تم حظرك من استخدام البوت")
                return
        except UserNotParticipant:
            invite_link = f"https://t.me/{MUST_JOIN}"
            await msg.reply_text(
                f"⚠️ **يجب الاشتراك في القناة أولاً**\n\n"
                f"اشترك هنا: {invite_link}\n\n"
                "بعد الاشتراك، اضغط على /login مرة أخرى",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 انضم للقناة", url=invite_link)],
                    [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
                ])
            )
            return
    
    nr = await msg.reply_text("**.... نورا بوتس ....**")
    await edit_nrbots(nr)
    await asyncio.sleep(0.4)
    await nr.delete()
    
    await msg.reply(
        f"مرحباً {msg.from_user.mention}!\n\n"
        "لمزيد من الأمان لحسابك، يجب أن تزودني بـ API ID و API Hash لتسجيل الدخول إلى حسابك\n\n"
        "⚠️ **يرجى تسجيل الدخول إلى حساب وهمي، ولا تستخدم حسابك الحقيقي** ⚠️\n\n"
        "شاهد طريقة الحصول على API ID و API Hash:\n"
        "https://youtu.be/NsbhYHz7K_w"
    )
    await asyncio.sleep(2)
    
    chat = msg.chat
    api = await bot.ask(chat.id, API_TEXT)
    
    if await is_cancel(msg, api.text):
        return
    try:
        check_api = int(api.text)
    except Exception:
        await msg.reply("`APP_ID` غير صالح.\nاضغط على /login لتسجيل مرة أخرى.")
        return
    api_id = api.text
    
    hash = await bot.ask(chat.id, HASH_TEXT)
    if await is_cancel(msg, hash.text):
        return
    if not len(hash.text) >= 30:
        await msg.reply("`API_HASH` غير صالح.\nاضغط على /login لتسجيل مرة أخرى")
        return
    api_hash = hash.text
    
    while True:
        number = await bot.ask(chat.id, PHONE_NUMBER_TEXT)
        if not number.text:
            continue
        if await is_cancel(msg, number.text):
            return
        phone = number.text
        confirm = await bot.ask(
            chat.id, 
            f'هل الرقم "{phone}" صحيح؟ (y/n): \n\n'
            f'أرسل: `y` (إذا كان الرقم صحيح)\n'
            f'أرسل: `n` (إذا كان الرقم خطأ)'
        )
        if await is_cancel(msg, confirm.text):
            return
        confirm = confirm.text.lower()
        if confirm == "y":
            break
            
    try:
        client = Client(f"{chat.id}_account", api_id=api_id, api_hash=api_hash, in_memory=True)
    except Exception as e:
        await bot.send_message(chat.id ,f"**خطأ:** `{str(e)}`\nاضغط /login للبدء مرة أخرى.")
        return
        
    try:
        await client.connect()
    except ConnectionError:
        await client.disconnect()
        await client.connect()
        
    try:
        code = await client.send_code(phone)
        await asyncio.sleep(1)
    except FloodWait1 as e:
        await msg.reply(f"حسابك لديه انتظار لمدة {e.value} ثانية. يرجى المحاولة بعد {e.value} ثانية")
        return
    except ApiIdInvalid1:
        await msg.reply("APP ID و API Hash غير صالحين.\n\nاضغط /login للبدء مرة أخرى.")
        return
    except PhoneNumberInvalid1:
        await msg.reply("رقم الهاتف غير صحيح.\n\nاضغط /login للبدء مرة أخرى.")
        return
        
    try:
        otp_msg = """
تم إرسال رمز مكون من 5 أرقام إلى رقم هاتفك.
الرجاء إرسال الرمز بالتنسيق: 1 2 3 4 5 (مسافة بين كل رقم!)

إذا لم يصلك الرمز، حاول إعادة تشغيل البوت واستخدام الأمر /start مرة أخرى.
اضغط /cancel للإلغاء.
"""
        otp = await bot.ask(chat.id, otp_msg, timeout=300)
    except asyncio.exceptions.TimeoutError:
        await msg.reply("انتهى الوقت المحدد (5 دقائق).\nاضغط /login للبدء من جديد")
        return
        
    if await is_cancel(msg, otp.text):
        return
    otp_code = otp.text
    
    try:
        await client.sign_in(phone, code.phone_code_hash, phone_code=' '.join(str(otp_code)))
    except PhoneCodeInvalid1:
        await msg.reply("الرمز غير صالح.\n\nاضغط /login للبدء من جديد.")
        return
    except PhoneCodeExpired1:
        await msg.reply("الرمز منتهي الصلاحية.\n\nاضغط /login للبدء من جديد.")
        return
    except SessionPasswordNeeded1:
        try:
            two_step_msg = """
حسابك محمي بالتحقق بخطوتين.
أرسل رمز التحقق بخطوتين.

اضغط /cancel للإلغاء.
"""
            two_step_code = await bot.ask(chat.id, two_step_msg, timeout=300)
        except asyncio.exceptions.TimeoutError:
            await msg.reply("انتهى الوقت المحدد (5 دقائق).\nاضغط /login للبدء من جديد.")
            return
            
        if await is_cancel(msg, two_step_code.text):
            return
        new_code = two_step_code.text
        try:
            await client.check_password(new_code)
        except Exception as e:
            await msg.reply(f"**خطأ:** `{str(e)}`")
            return
    except Exception as e:
        await bot.send_message(chat.id ,f"**خطأ:** `{str(e)}`")
        return
        
    try:
        session_string = await client.export_session_string()
        await bot.send_message(chat.id, "✅ تم توصيل حسابك بنجاح")
        await db.set_session(chat.id, session_string)
        await db.set_api(chat.id, api_id)
        await db.set_hash(chat.id, api_hash)
        await db.set_login(chat.id, True)
        await client.disconnect()
        
        # زر للانتقال إلى نقل الأعضاء
        await msg.reply(
            "🎉 **تم التسجيل بنجاح!**\n\n"
            "يمكنك الآن استخدام الأمر /memadd لبدء نقل الأعضاء",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd")],
                [InlineKeyboardButton("📊 حالة الحساب", callback_data="status")]
            ])
        )
    except Exception as e:
        await bot.send_message(chat.id ,f"**خطأ:** `{str(e)}`")
        return

async def add(msg, src, dest, count: int, type):
    userid = msg.from_user.id
    nr = await msg.reply_text("**........**")
    await edit_ini(nr)

    try:
        cc = 0
        session = await db.get_session(userid)
        api = await db.get_api(userid) 
        hash = await db.get_hash(userid) 

        app = Client(name=userid, session_string=session, api_id=api, api_hash=hash)
        await nr.edit_text("**.... بدء تشغيل العميل ....**")
        
        await app.start()
        await edit_starting(nr)

        try:
            await app.join_chat(src)
        except Exception as e:
            LOGS.warning(f"لا يمكن الانضمام إلى الدردشة المصدر {src}: {e}")

        chat = await app.get_chat(src)
        schat_id = chat.id
        
        xx = await app.get_chat(dest)
        tt = xx.members_count
        dchat_id = xx.id
        await app.join_chat(dchat_id)
        start_time = time.time()
        await asyncio.sleep(3)

    except Exception as e:
        e = str(e)
        if "Client has not been started yet" in e:
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("العميل لم يبدأ بعد", reply_markup=keyboard)
        elif "403 USER_PRIVACY_RESTRICTED" in e:
            await nr.edit_text("فشل الإضافة بسبب إعدادات الخصوصية", reply_markup=keyboard)
            await asyncio.sleep(1)
        elif "400 CHAT_ADMIN_REQUIRED" in e:
            await nr.edit_text("صلاحيات المسؤول مطلوبة. يرجى التأكد من أن المجموعة عامة أو أن حسابك مسؤول فيها.", reply_markup=keyboard)
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("فشل الحصول على الأعضاء من المجموعة المصدر", reply_markup=keyboard)
        elif "400 INVITE_REQUEST_SENT" in e:
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("لا يمكنني إضافة أعضاء من مجموعة تتطلب موافقة المسؤول للانضمام.", reply_markup=keyboard)
        elif "400 PEER_FLOOD" in e:
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("تم إيقاف الإضافة بسبب 400 PEER_FLOOD\n\nحسابك محدود، يرجى الانتظار بعض الوقت ثم المحاولة مرة أخرى.", reply_markup=keyboard)
        elif "401 AUTH_KEY_UNREGISTERED" in e:
            await db.set_session(msg.from_user.id, "")
            await db.set_login(msg.from_user.id, False)
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("يرجى تسجيل الدخول مرة أخرى لاستخدام هذه الميزة", reply_markup=keyboard)
        elif "403 CHAT_WRITE_FORBIDDEN" in e:
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("ليس لديك صلاحية إرسال رسائل في هذه الدردشة\nيرجى جعل حساب المستخدم مسؤولاً وحاول مرة أخرى", reply_markup=keyboard)
        elif "400 CHANNEL_INVALID" in e:
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("معرف المصدر أو الوجهة غير صالح", reply_markup=keyboard)
        elif "400 USERNAME_NOT_OCCUPIED" in e:
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("المعرف غير مستخدم من قبل أي شخص، يرجى التحقق من المعرف أو userid الذي قدمته", reply_markup=keyboard)
        elif "401 SESSION_REVOKED" in e:
            await db.set_session(msg.from_user.id, "")
            await db.set_login(msg.from_user.id, False)
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text("لقد أنهيت جلسة التسجيل من حساب المستخدم\n\nيرجى تسجيل الدخول مرة أخرى", reply_markup=keyboard)
        return await nr.edit_text(f"**خطأ:** `{str(e)}`", reply_markup=keyboard)

    if type == "a":
        try:
            await nr.edit_text("**.... بدء إضافة الأعضاء النشطين ....**")
            await edit_active(nr)
            await asyncio.sleep(0.5)
            async for member in app.get_chat_members(schat_id):
                user = member.user
                s = ["RECENTLY","ONLINE"]
                if user.is_bot:
                    pass
                else:
                    b = (str(user.status)).split(".")[1]
                    if b in s:
                        try:
                            user_id = user.id
                            await nr.edit_text(f'جاري إضافة: `{user_id}`')
                            if await app.add_chat_members(dchat_id, user_id):
                                cc = cc + 1
                                await nr.edit_text(f'تمت الإضافة: `{user_id}`')
                                await asyncio.sleep(5)
                        except FloodWait1 as fl:
                            t = "تم اكتشاف انتظار Floodwait في حساب المستخدم\n\nتم إيقاف عملية الإضافة"
                            await nr.edit_text(t)
                            x2 = await app.get_chat(dchat_id)
                            t2 = x2.members_count
                            completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
                            ttext = f"""
<u>**✨ تم إيقاف عملية الإضافة بسبب Floodwait لمدة {fl.value} ثانية ✨**</u>

    ┏━━━━━━━━━━━━━━━━━┓
    ┣✨ تمت الإضافة إلى الدردشة: `{dchat_id}`
    ┣✨ عدد الأعضاء السابق: **{tt}**
    ┣✨ عدد الأعضاء الحالي: **{t2}**
    ┣✨ إجمالي المستخدمين المضافين: **{cc}**
    ┣✨ الوقت المستغرق: **{completed_in}**
    ┗━━━━━━━━━━━━━━━━━┛
"""
                            await app.leave_chat(src)
                            await app.stop()
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text(ttext, reply_markup=keyboard)
                        except Exception as e:
                            e = str(e)
                            if "Client has not been started yet" in e:
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("العميل لم يبدأ بعد", reply_markup=keyboard)
                            elif "403 USER_PRIVACY_RESTRICTED" in e:
                                await nr.edit_text("فشل الإضافة بسبب إعدادات الخصوصية")
                                await asyncio.sleep(1)
                            elif "400 CHAT_ADMIN_REQUIRED" in e:
                                await nr.edit_text("صلاحيات المسؤول مطلوبة. يرجى التأكد من أن المجموعة عامة أو أن حسابك مسؤول فيها.", reply_markup=keyboard)
                                await app.stop()
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return
                            elif "400 INVITE_REQUEST_SENT" in e:
                                await app.stop()
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("لا يمكنني إضافة أعضاء من مجموعة تتطلب موافقة المسؤول للانضمام.", reply_markup=keyboard)
                            elif "400 PEER_FLOOD" in e:
                                await app.stop()
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("تم إيقاف الإضافة بسبب 400 PEER_FLOOD\n\nحسابك محدود، يرجى الانتظار بعض الوقت ثم المحاولة مرة أخرى.", reply_markup=keyboard)
                            elif "401 AUTH_KEY_UNREGISTERED" in e:
                                await app.stop()
                                await db.set_session(msg.from_user.id, "")
                                await db.set_login(msg.from_user.id, False)
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("يرجى تسجيل الدخول مرة أخرى لاستخدام هذه الميزة", reply_markup=keyboard)
                            elif "403 CHAT_WRITE_FORBIDDEN" in e:
                                await app.stop()
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("ليس لديك صلاحية إضافة أعضاء في هذه الدردشة\nيرجى جعل حسابك مسؤولاً وحاول مرة أخرى", reply_markup=keyboard)
                            elif "400 CHANNEL_INVALID" in e:
                                await app.stop()
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("معرف المصدر أو الوجهة غير صالح", reply_markup=keyboard)
                            elif "400 USERNAME_NOT_OCCUPIED" in e:
                                await app.stop()
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("المعرف غير مستخدم من قبل أي شخص، يرجى التحقق من المعرف أو userid الذي قدمته", reply_markup=keyboard)
                            elif "401 SESSION_REVOKED" in e:
                                await app.stop()
                                await db.set_session(msg.from_user.id, "")
                                await db.set_login(msg.from_user.id, False)
                                remove_if_exists(f"{msg.from_user.id}_account.session")
                                return await nr.edit_text("لقد أنهيت جلسة التسجيل من حساب المستخدم\n\nيرجى تسجيل الدخول مرة أخرى", reply_markup=keyboard)
                            else:
                                await nr.edit_text(f'فشلت الإضافة \n\n**خطأ:** `{str(e)}`')
                                await asyncio.sleep(5)

                if cc == count:
                    x2 = await app.get_chat(dchat_id)
                    t2 = x2.members_count
                    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
                    ttext = f"""
<u>**✨ تم الانتهاء من عملية الإضافة بنجاح ✨**</u>

    ┏━━━━━━━━━━━━━━━━━┓
    ┣✨ تمت الإضافة إلى الدردشة: `{dchat_id}`
    ┣✨ عدد الأعضاء السابق: **{tt}**
    ┣✨ عدد الأعضاء الحالي: **{t2}**
    ┣✨ إجمالي المستخدمين المضافين: **{cc}**
    ┣✨ الوقت المستغرق: **{completed_in}**
    ┗━━━━━━━━━━━━━━━━━┛
"""
                    await app.leave_chat(src)
                    await app.stop()
                    remove_if_exists(f"{msg.from_user.id}_account.session")
                    return await nr.edit_text(ttext, reply_markup=keyboard)

        except Exception as e:
            e = str(e)
            if "Client has not been started yet" in e:
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("العميل لم يبدأ بعد", reply_markup=keyboard)
            elif "403 USER_PRIVACY_RESTRICTED" in e:
                await nr.edit_text("فشل الإضافة بسبب إعدادات الخصوصية", reply_markup=keyboard)
                await asyncio.sleep(1)
            elif "400 CHAT_ADMIN_REQUIRED" in e:
                await nr.edit_text("فشل الإضافة لأن هذه الطريقة تتطلب صلاحيات مسؤول الدردشة.\n\nيرجى جعل حسابك مسؤولاً في المجموعة وحاول مرة أخرى", reply_markup=keyboard)
            elif "400 INVITE_REQUEST_SENT" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("لا يمكنني إضافة أعضاء من مجموعة تتطلب موافقة المسؤول للانضمام.", reply_markup=keyboard)
            elif "400 PEER_FLOOD" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("تم إيقاف الإضافة بسبب 400 PEER_FLOOD\n\nحسابك محدود، يرجى الانتظار بعض الوقت ثم المحاولة مرة أخرى.", reply_markup=keyboard)
            elif "401 AUTH_KEY_UNREGISTERED" in e:
                await app.stop()
                await db.set_session(msg.from_user.id, "")
                await db.set_login(msg.from_user.id, False)
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("يرجى تسجيل الدخول مرة أخرى لاستخدام هذه الميزة", reply_markup=keyboard)
            elif "403 CHAT_WRITE_FORBIDDEN" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("ليس لديك صلاحية إرسال رسائل في هذه الدردشة\nيرجى جعل حساب المستخدم مسؤولاً وحاول مرة أخرى", reply_markup=keyboard)
            elif "400 CHANNEL_INVALID" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("معرف المصدر أو الوجهة غير صالح", reply_markup=keyboard)
            elif "400 USERNAME_NOT_OCCUPIED" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("المعرف غير مستخدم من قبل أي شخص، يرجى التحقق من المعرف أو userid الذي قدمته", reply_markup=keyboard)
            elif "401 SESSION_REVOKED" in e:
                await app.stop()
                await db.set_session(msg.from_user.id, "")
                await db.set_login(msg.from_user.id, False)
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("لقد أنهيت جلسة التسجيل من حساب المستخدم\n\nيرجى تسجيل الدخول مرة أخرى", reply_markup=keyboard)
            await app.stop()
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text(f"**خطأ:** `{str(e)}`", reply_markup=keyboard)

    elif type == "m":
        try:
            await nr.edit_text("**.... بدء إضافة الأعضاء المختلطين ....**")
            await edit_mixed(nr)
            await asyncio.sleep(0.5)
            async for member in app.get_chat_members(schat_id):
                user = member.user
                if user.is_bot:
                    pass
                else:
                    try:
                        user_id = user.id
                        await nr.edit_text(f'جاري إضافة: `{user_id}`')
                        if await app.add_chat_members(dchat_id, user_id):
                            cc = cc + 1
                            await nr.edit_text(f'تمت الإضافة: `{user_id}`')
                            await asyncio.sleep(5)
                    except FloodWait1 as fl:
                        t = "تم اكتشاف انتظار Floodwait في حساب المستخدم\n\nتم إيقاف عملية الإضافة"
                        await nr.edit_text(t)
                        x2 = await app.get_chat(dchat_id)
                        t2 = x2.members_count
                        completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
                        ttext = f"""
<u>**✨ تم إيقاف عملية الإضافة بسبب Floodwait لمدة {fl.value} ثانية ✨**</u>

    ┏━━━━━━━━━━━━━━━━━┓
    ┣✨ تمت الإضافة إلى الدردشة: `{dchat_id}`
    ┣✨ عدد الأعضاء السابق: **{tt}**
    ┣✨ عدد الأعضاء الحالي: **{t2}**
    ┣✨ إجمالي المستخدمين المضافين: **{cc}**
    ┣✨ الوقت المستغرق: **{completed_in}**
    ┗━━━━━━━━━━━━━━━━━┛
"""
                        await app.leave_chat(src)
                        await app.stop()
                        remove_if_exists(f"{msg.from_user.id}_account.session")
                        return await nr.edit_text(ttext, reply_markup=keyboard)
                    except Exception as e:
                        e = str(e)
                        if "Client has not been started yet" in e:
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("العميل لم يبدأ بعد", reply_markup=keyboard)
                        elif "403 USER_PRIVACY_RESTRICTED" in e:
                            await nr.edit_text("فشل الإضافة بسبب إعدادات الخصوصية")
                            await asyncio.sleep(1)
                        elif "400 CHAT_ADMIN_REQUIRED" in e:
                            await nr.edit_text("فشل الإضافة لأن هذه الطريقة تتطلب صلاحيات مسؤول الدردشة.\n\nيرجى جعل حسابك مسؤولاً في المجموعة وحاول مرة أخرى", reply_markup=keyboard)
                        elif "400 INVITE_REQUEST_SENT" in e:
                            await app.stop()
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("لا يمكنني إضافة أعضاء من مجموعة تتطلب موافقة المسؤول للانضمام.", reply_markup=keyboard)
                        elif "400 PEER_FLOOD" in e:
                            await app.stop()
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("تم إيقاف الإضافة بسبب 400 PEER_FLOOD\n\nحسابك محدود، يرجى الانتظار بعض الوقت ثم المحاولة مرة أخرى.", reply_markup=keyboard)
                        elif "401 AUTH_KEY_UNREGISTERED" in e:
                            await app.stop()
                            await db.set_session(msg.from_user.id, "")
                            await db.set_login(msg.from_user.id, False)
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("يرجى تسجيل الدخول مرة أخرى لاستخدام هذه الميزة", reply_markup=keyboard)
                        elif "403 CHAT_WRITE_FORBIDDEN" in e:
                            await app.stop()
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("ليس لديك صلاحية إضافة أعضاء في هذه الدردشة\nيرجى جعل حسابك مسؤولاً وحاول مرة أخرى", reply_markup=keyboard)
                        elif "400 CHANNEL_INVALID" in e:
                            await app.stop()
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("معرف المصدر أو الوجهة غير صالح", reply_markup=keyboard)
                        elif "400 USERNAME_NOT_OCCUPIED" in e:
                            await app.stop()
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("المعرف غير مستخدم من قبل أي شخص، يرجى التحقق من المعرف أو userid الذي قدمته", reply_markup=keyboard)
                        elif "401 SESSION_REVOKED" in e:
                            await app.stop()
                            await db.set_session(msg.from_user.id, "")
                            await db.set_login(msg.from_user.id, False)
                            remove_if_exists(f"{msg.from_user.id}_account.session")
                            return await nr.edit_text("لقد أنهيت جلسة التسجيل من حساب المستخدم\n\nيرجى تسجيل الدخول مرة أخرى", reply_markup=keyboard)
                        else:
                            await nr.edit_text(f'فشلت الإضافة \n\n**خطأ:** `{str(e)}`')
                            await asyncio.sleep(5)

                if cc == count:
                    x2 = await app.get_chat(dchat_id)
                    t2 = x2.members_count
                    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
                    ttext = f"""
<u>**✨ تم الانتهاء من عملية الإضافة بنجاح ✨**</u>

    ┏━━━━━━━━━━━━━━━━━┓
    ┣✨ تمت الإضافة إلى الدردشة: `{dchat_id}`
    ┣✨ عدد الأعضاء السابق: **{tt}**
    ┣✨ عدد الأعضاء الحالي: **{t2}**
    ┣✨ إجمالي المستخدمين المضافين: **{cc}**
    ┣✨ الوقت المستغرق: **{completed_in}**
    ┗━━━━━━━━━━━━━━━━━┛
"""
                    await app.leave_chat(src)
                    await app.stop()
                    remove_if_exists(f"{msg.from_user.id}_account.session")
                    return await nr.edit_text(ttext, reply_markup=keyboard)

        except Exception as e:
            e = str(e)
            if "Client has not been started yet" in e:
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("العميل لم يبدأ بعد", reply_markup=keyboard)
            elif "403 USER_PRIVACY_RESTRICTED" in e:
                await nr.edit_text("فشل الإضافة بسبب إعدادات الخصوصية", reply_markup=keyboard)
                await asyncio.sleep(1)
            elif "400 CHAT_ADMIN_REQUIRED" in e:
                await nr.edit_text("فشل الإضافة لأن هذه الطريقة تتطلب صلاحيات مسؤول الدردشة.\n\nيرجى جعل حسابك مسؤولاً في المجموعة وحاول مرة أخرى", reply_markup=keyboard)
            elif "400 INVITE_REQUEST_SENT" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("لا يمكنني إضافة أعضاء من مجموعة تتطلب موافقة المسؤول للانضمام.", reply_markup=keyboard)
            elif "400 PEER_FLOOD" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("تم إيقاف الإضافة بسبب 400 PEER_FLOOD\n\nحسابك محدود، يرجى الانتظار بعض الوقت ثم المحاولة مرة أخرى.", reply_markup=keyboard)
            elif "401 AUTH_KEY_UNREGISTERED" in e:
                await app.stop()
                await db.set_session(msg.from_user.id, "")
                await db.set_login(msg.from_user.id, False)
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("يرجى تسجيل الدخول مرة أخرى لاستخدام هذه الميزة", reply_markup=keyboard)
            elif "403 CHAT_WRITE_FORBIDDEN" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("ليس لديك صلاحية إرسال رسائل في هذه الدردشة\nيرجى جعل حساب المستخدم مسؤولاً وحاول مرة أخرى", reply_markup=keyboard)
            elif "400 CHANNEL_INVALID" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("معرف المصدر أو الوجهة غير صالح", reply_markup=keyboard)
            elif "400 USERNAME_NOT_OCCUPIED" in e:
                await app.stop()
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("المعرف غير مستخدم من قبل أي شخص، يرجى التحقق من المعرف أو userid الذي قدمته", reply_markup=keyboard)
            elif "401 SESSION_REVOKED" in e:
                await app.stop()
                await db.set_session(msg.from_user.id, "")
                await db.set_login(msg.from_user.id, False)
                remove_if_exists(f"{msg.from_user.id}_account.session")
                return await nr.edit_text("لقد أنهيت جلسة التسجيل من حساب المستخدم\n\nيرجى تسجيل الدخول مرة أخرى", reply_markup=keyboard)
            await app.stop()
            remove_if_exists(f"{msg.from_user.id}_account.session")
            return await nr.edit_text(f"**خطأ:** `{str(e)}`", reply_markup=keyboard)

@bot.on_message(filters.private & filters.command("memadd"))
async def NewChat(client, msg):
    # التحقق من الاشتراك الإجباري
    if FORCE_SUBS:
        try:
            user = await bot.get_chat_member(MUST_JOIN, msg.from_user.id)
            if user.status == "kicked":
                await msg.reply_text("❌ تم حظرك من استخدام البوت")
                return
        except UserNotParticipant:
            invite_link = f"https://t.me/{MUST_JOIN}"
            await msg.reply_text(
                f"⚠️ **يجب الاشتراك في القناة أولاً**\n\n"
                f"اشترك هنا: {invite_link}\n\n"
                "بعد الاشتراك، اضغط على /memadd مرة أخرى",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 انضم للقناة", url=invite_link)],
                    [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
                ])
            )
            return
    
    try:
        chat = msg.chat
        nr = await msg.reply_text(".... نورا بوتس ....")
        await edit_nrbots(nr)
        userr = msg.from_user.id
        if not await db.get_session(userr):
            await nr.delete()
            return await msg.reply_text(
                "⚠️ **يجب تسجيل الدخول أولاً**\n\n"
                "استخدم الأمر /login لتسجيل الدخول إلى حسابك",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")]
                ])
            )

        await nr.delete()
        while True:
            src_raw = await bot.ask(chat.id, "أرسل لي الآن رابط المجموعة العامة التي تريد نقل الأعضاء منها.")
            if not src_raw.text:
                continue
            if await is_cancel(msg, src_raw.text):
                return
            src = if_url(src_raw.text)
            
            dest_raw = await bot.ask(chat.id, "أرسل لي الآن رابط المجموعة العامة التي تريد إضافة الأعضاء إليها.")
            if await is_cancel(msg, dest_raw.text):
                return
            dest = if_url(dest_raw.text)
            
            quant_raw = await bot.ask(chat.id, "أرسل لي الآن الكمية. كم عدد الأعضاء الذي تريد إضافتها إلى مجموعتك؟\n\nمثال: ارسل 5\n\nلأمان حسابك ضد الحظر، يرجى إدخال رقم أقل من 20")
            if await is_cancel(msg, quant_raw.text):
                return
            quant = int(quant_raw.text)
            
            type_raw = await bot.ask(chat.id, 
                f'اختر الآن نوع الأعضاء الذي تريد نقله من مجموعة `{src}`\n\n'
                f'لنقل أعضاء 👤 نشطين 👤 أرسل `a`\n'
                f'لنقل أعضاء 👥 مختلطين 👥 أرسل `m`\n\n'
                f'أرسل: `a` (إذا كنت تريد أعضاء نشطين)\n'
                f'أرسل: `m` (إذا كنت تريد أعضاء مختلطين)'
            )
            if await is_cancel(msg, type_raw.text):
                return
            type = type_raw.text.lower()

            confirm = await bot.ask(chat.id, 
                f'أنت تريد إضافة `{quant}` {"`👤 أعضاء نشطين 👤`" if type == "a" else "`👥 أعضاء مختلطين 👥`"} من مجموعة `{src}` إلى مجموعتك `{dest}`\n\n'
                f'هل أنت متأكد من المتابعة؟ (y/n):\n\n'
                f'أرسل: `y` (نعم)\n'
                f'أرسل: `n` (لا)'
            )
            if await is_cancel(msg, confirm.text):
                return
            confirm = confirm.text.lower()
            if confirm == "y":
                break
                
        try:
            await add(msg, src=src, dest=dest, count=quant, type=type)
        except Exception as e:
            return await msg.reply_text(f"**خطأ:** `{str(e)}`", reply_markup=keyboard)
    except Exception as e:
        return await msg.reply_text(f"**خطأ:** `{str(e)}`", reply_markup=keyboard)

@bot.on_message(filters.private & filters.command("status"))
async def logoutt(client, message: Message):
    # التحقق من الاشتراك الإجباري
    if FORCE_SUBS:
        try:
            user = await bot.get_chat_member(MUST_JOIN, message.from_user.id)
            if user.status == "kicked":
                await message.reply_text("❌ تم حظرك من استخدام البوت")
                return
        except UserNotParticipant:
            invite_link = f"https://t.me/{MUST_JOIN}"
            await message.reply_text(
                f"⚠️ **يجب الاشتراك في القناة أولاً**\n\n"
                f"اشترك هنا: {invite_link}\n\n"
                "بعد الاشتراك، اضغط على /status مرة أخرى",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 انضم للقناة", url=invite_link)],
                    [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
                ])
            )
            return
    
    nr = await message.reply_text("جاري التحقق...")
    user_id = message.from_user.id
    if await db.get_session(user_id):
        try:    
            session = await db.get_session(user_id) 
            api_id = await db.get_api(user_id) 
            api_hash = await db.get_hash(user_id) 
            app = Client(name=user_id, session_string=f"{session}", api_id=api_id, api_hash=api_hash, in_memory=True) 
            await app.start()
            await app.get_me()
            xx = await app.get_me()
            op = xx.first_name
            id = xx.id
            await app.stop()

            status_text = f"""
**📊 معلومات الحساب المسجل**

**الاسم:** {op}
**الرقم التعريفي:** {id}
**حالة التسجيل:** ✅ نشط

**خيارات الإدارة:**
"""
            await nr.edit_text(
                status_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔓 تسجيل الخروج", callback_data="logout_confirm")],
                    [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd")],
                    [InlineKeyboardButton("❌ إغلاق", callback_data="close")]
                ])
            )
        except ApiIdInvalid1:
            try:
                session = await db.get_session(user_id) 
                app = Client(name=user_id, session_string=f"{session}", api_id=API_ID, api_hash=API_HASH)
                await app.start()
                await app.get_me()
                xx = await app.get_me()
                op = xx.first_name
                id = xx.id
                await app.stop()
                
                status_text = f"""
**📊 معلومات الحساب المسجل**

**الاسم:** {op}
**الرقم التعريفي:** {id}
**حالة التسجيل:** ✅ نشط

**خيارات الإدارة:**
"""
                await nr.edit_text(
                    status_text,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔓 تسجيل الخروج", callback_data="logout_confirm")],
                        [InlineKeyboardButton("👥 نقل الأعضاء", callback_data="memadd")],
                        [InlineKeyboardButton("❌ إغلاق", callback_data="close")]
                    ])
                )
            except Exception as e:
                return await nr.edit_text(f'**خطأ:** {e}')
        except Exception as e:
            return await nr.edit_text(f'**خطأ:** {e}')
    else:        
        await nr.edit_text(
            '⚠️ **لم يتم تسجيل الدخول بعد**\n\n'
            'يجب تسجيل الدخول لاستخدام جميع ميزات البوت',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
                [InlineKeyboardButton("📚 المساعدة", callback_data="help")],
                [InlineKeyboardButton("❌ إغلاق", callback_data="close")]
            ])
        )

# باقي الأوامر والإعدادات تبقى كما هي مع الترجمة للعربية
# ... [يتبع باقي الكود بنفس النمط]

@bot.on_callback_query(filters.regex("home"))
async def cb_home(client, update):
    await update.message.edit_text(
        text=START.format(update.from_user.mention),
        disable_web_page_preview=True,
        reply_markup=START_BUTTONS
    )

@bot.on_callback_query(filters.regex("help"))
async def cb_help(client, update):
    await update.message.edit_text(
        text=HELP,
        disable_web_page_preview=True,
        reply_markup=HELP_BUTTONS
    )

@bot.on_callback_query(filters.regex("close"))
async def cb_close(client, update):
    await update.message.delete()

@bot.on_callback_query(filters.regex("login"))
async def cb_login(client, update):
    await update.message.edit_text(
        "🔐 **تسجيل الدخول**\n\n"
        "سيتم بدء عملية تسجيل الدخول إلى حسابك.\n\n"
        "اضغط على الزر أدناه للمتابعة:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 بدء التسجيل", callback_data="start_login")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
        ])
    )

@bot.on_callback_query(filters.regex("start_login"))
async def cb_start_login(client, update):
    await update.message.delete()
    # استدعاء وظيفة التسجيل
    await genStr(client, update)

@bot.on_callback_query(filters.regex("memadd"))
async def cb_memadd(client, update):
    await update.message.edit_text(
        "👥 **نقل الأعضاء**\n\n"
        "سيتم بدء عملية نقل الأعضاء بين المجموعات.\n\n"
        "اضغط على الزر أدناه للمتابعة:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 بدء النقل", callback_data="start_memadd")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
        ])
    )

@bot.on_callback_query(filters.regex("start_memadd"))
async def cb_start_memadd(client, update):
    await update.message.delete()
    # استدعاء وظيفة نقل الأعضاء
    await NewChat(client, update)

@bot.on_callback_query(filters.regex("status"))
async def cb_status(client, update):
    await update.message.delete()
    # استدعاء وظيفة الحالة
    await logoutt(client, update)

@bot.on_callback_query(filters.regex("logout_confirm"))
async def cb_logout_confirm(client, update):
    await update.message.edit_text(
        "⚠️ **تأكيد تسجيل الخروج**\n\n"
        "هل أنت متأكد من أنك تريد تسجيل الخروج؟\n"
        "سيتم مسح جميع بيانات تسجيل الدخول.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم، سجل الخروج", callback_data="confirm_logout")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="status")]
        ])
    )

@bot.on_callback_query(filters.regex("confirm_logout"))
async def cb_confirm_logout(client, update):
    user_id = update.from_user.id
    await db.set_session(user_id, "")
    await db.set_login(user_id, False)
    await update.message.edit_text(
        "✅ **تم تسجيل الخروج بنجاح**\n\n"
        "تم مسح بيانات تسجيل الدخول بنجاح.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")]
        ])
    )

@bot.on_callback_query(filters.regex("check_sub"))
async def cb_check_sub(client, update):
    user_id = update.from_user.id
    try:
        user = await bot.get_chat_member(MUST_JOIN, user_id)
        if user.status == "kicked":
            await update.message.edit_text(
                "❌ **تم حظرك من القناة**\n\n"
                "لا يمكنك استخدام البوت.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 قناة البوت", url=f"https://t.me/{MUST_JOIN}")]
                ])
            )
        else:
            await update.message.edit_text(
                "✅ **تم الاشتراك بنجاح**\n\n"
                "يمكنك الآن استخدام البوت.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 ابدأ الاستخدام", callback_data="home")]
                ])
            )
    except UserNotParticipant:
        await update.message.edit_text(
            "❌ **لم تشترك بعد**\n\n"
            "يجب الاشتراك في القناة أولاً.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 انضم للقناة", url=f"https://t.me/{MUST_JOIN}")],
                [InlineKeyboardButton("🔄 تحقق مرة أخرى", callback_data="check_sub")]
            ])
        )

# -----------------------------------------------------------------------------
# 9. نقطة الدخول
# -----------------------------------------------------------------------------

async def main():
    try:   
        print("جاري بدء تشغيل البوت...")
        LOGS.info("جاري بدء تشغيل البوت...")

        await bot.start()
        app = web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app, bind_address, PORT).start()

        b = await getme()
        
        LOGS.info(f"@{b} بدء التشغيل...")
        print(f"@{b} بدء التشغيل...")
        
        # إرسال رسالة بدء التشغيل إلى قناة السجلات
        try:
            await bot.send_message(
                LOG_CHANNEL,
                f"✅ **تم بدء تشغيل البوت بنجاح**\n\n"
                f"**اسم البوت:** @{b}\n"
                f"**وقت البدء:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"**الإصدار:** 2.0 العربية"
            )
        except Exception as e:
            print(f"خطأ في إرسال رسالة البدء: {e}")
        
        await idle()
    except Exception as e:
        print(f"خطأ في التشغيل: {e}")
        LOGS.warning(e)

if __name__ == "__main__":
    bot.run(main())
