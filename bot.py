import asyncio
import sqlite3
import re
from datetime import datetime
from typing import Dict, List, Optional
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    CallbackQuery
)
from pyrogram.errors import (
    BadRequest, 
    FloodWait, 
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneCodeExpired
)

# بيانات API
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
BOT_TOKEN = "8398354970:AAHqgmpKPptjDgI_Ogs1fKnBgfPi4N8SoR4"

# إعدادات المدير
ADMIN_ID = 6689435577
MANDATORY_CHANNEL = "iIl337"
CODE_CHANNEL = "+42777"

# حالات المحادثة
class ConversationState:
    SETTING_INTERVAL = "setting_interval"
    SETTING_MESSAGE = "setting_message"
    LOGIN_PHONE = "login_phone"
    LOGIN_CODE = "login_code"
    LOGIN_PASSWORD = "login_password"
    SELECTING_GROUPS = "selecting_groups"

# تهيئة البوت
app = Client("auto_poster_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# تخزين البيانات
user_states = {}
user_data = {}
temp_sessions = {}

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  invited_by INTEGER,
                  invite_count INTEGER DEFAULT 0,
                  is_active INTEGER DEFAULT 0,
                  invite_code TEXT,
                  join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # جدول الإعدادات
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                 (user_id INTEGER PRIMARY KEY,
                  interval INTEGER DEFAULT 60,
                  message TEXT,
                  selected_groups TEXT)''')
    
    # جدول الجلسات
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions
                 (user_id INTEGER PRIMARY KEY,
                  session_string TEXT)''')
    
    # جدول الأرقام للمدير
    c.execute('''CREATE TABLE IF NOT EXISTS user_numbers
                 (user_id INTEGER PRIMARY KEY,
                  phone_number TEXT,
                  added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

# وظائف مساعدة للقاعدة البيانات
def get_user(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, invited_by=None):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    invite_code = f"INVITE_{user_id}_{int(datetime.now().timestamp())}"
    c.execute("INSERT OR IGNORE INTO users (user_id, invited_by, invite_code) VALUES (?, ?, ?)",
              (user_id, invited_by, invite_code))
    conn.commit()
    conn.close()
    return invite_code

def update_user_invites(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET invite_count = invite_count + 1 WHERE user_id = ?", (user_id,))
    c.execute("SELECT invite_count FROM users WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    
    if count >= 5:
        c.execute("UPDATE users SET is_active = 1 WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    return count

def get_user_settings(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    settings = c.fetchone()
    conn.close()
    return settings

def save_user_settings(user_id, interval=None, message=None, groups=None):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    if interval is not None:
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, interval) VALUES (?, ?)",
                  (user_id, interval))
    
    if message is not None:
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, message) VALUES (?, ?)",
                  (user_id, message))
    
    if groups is not None:
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, selected_groups) VALUES (?, ?)",
                  (user_id, groups))
    
    conn.commit()
    conn.close()

def save_session(user_id, session_string):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_sessions (user_id, session_string) VALUES (?, ?)",
              (user_id, session_string))
    conn.commit()
    conn.close()

def get_session(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT session_string FROM user_sessions WHERE user_id = ?", (user_id,))
    session = c.fetchone()
    conn.close()
    return session[0] if session else None

# التحقق من العضوية في القناة
async def check_channel_membership(user_id):
    try:
        user_client = await get_user_client(user_id)
        if user_client:
            member = await user_client.get_chat_member(MANDATORY_CHANNEL, user_id)
            return member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except Exception:
        pass
    return False

# الحصول على عميل المستخدم
async def get_user_client(user_id):
    session_string = get_session(user_id)
    if not session_string:
        return None
    
    try:
        client = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
        await client.start()
        return client
    except Exception:
        return None

# لوحة المفاتيح الرئيسية
def get_main_keyboard(user_id):
    user = get_user(user_id)
    if not user or user[3] == 0:  # إذا لم يكن مفعل
        keyboard = [
            [InlineKeyboardButton("توليد رابط دعوة", callback_data="generate_invite")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("ابدء النشر", callback_data="start_publishing")],
            [InlineKeyboardButton("اعداد النشر", callback_data="setup_publishing")]
        ]
    
    # زر التحقق من العضوية للجميع
    keyboard.append([InlineKeyboardButton("تحقق من العضوية", callback_data="check_membership")])
    
    return InlineKeyboardMarkup(keyboard)

# لوحة إعداد النشر
def get_setup_keyboard():
    keyboard = [
        [InlineKeyboardButton("تسجيل الدخول", callback_data="login_user")],
        [InlineKeyboardButton("تعيين الفاصل", callback_data="set_interval")],
        [InlineKeyboardButton("تعيين الرسالة", callback_data="set_message")],
        [InlineKeyboardButton("تعيين المجموعات", callback_data="set_groups")],
        [InlineKeyboardButton("التحكم بالحساب", callback_data="account_control")],
        [InlineKeyboardButton("رجوع", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# لوحة التحكم بالحساب
def get_account_control_keyboard():
    keyboard = [
        [InlineKeyboardButton("مغادرة القنوات", callback_data="leave_channels")],
        [InlineKeyboardButton("مغادرة المجموعات", callback_data="leave_groups")],
        [InlineKeyboardButton("رجوع", callback_data="back_to_setup")]
    ]
    return InlineKeyboardMarkup(keyboard)

# لوحة المدير
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("سحب رقم", callback_data="pull_number")],
        [InlineKeyboardButton("إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("إحصائيات البوت", callback_data="bot_stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

# معالجة الأمر /start
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    # التحقق من العضوية الإجبارية
    if not await check_channel_membership(user_id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("انضم إلى القناة", url=f"https://t.me/{MANDATORY_CHANNEL}")],
            [InlineKeyboardButton("تحقق من العضوية", callback_data="check_membership")]
        ])
        await message.reply_text(
            "⚠️ **عذراً، يجب عليك الانضمام إلى قناتنا أولاً**\n\n"
            "انضم إلى القناة ثم اضغط على زر التحقق:",
            reply_markup=keyboard
        )
        return
    
    # معالجة روابط الدعوة
    if len(message.command) > 1:
        invite_code = message.command[1]
        if invite_code.startswith("INVITE_"):
            # البحث عن صاحب الرابط
            conn = sqlite3.connect('bot.db')
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE invite_code = ?", (invite_code,))
            inviter = c.fetchone()
            
            if inviter:
                inviter_id = inviter[0]
                create_user(user_id, inviter_id)
                update_user_invites(inviter_id)
                
                await message.reply_text(
                    "✅ **تم تسجيلك بنجاح!**\n\n"
                    "شكراً للانضمام عبر رابط الدعوة.",
                    reply_markup=get_main_keyboard(user_id)
                )
            else:
                await message.reply_text(
                    "❌ **رابط الدعوة غير صحيح!**",
                    reply_markup=get_main_keyboard(user_id)
                )
            conn.close()
            return
    
    # إنشاء مستخدم جديد إذا لم يكن موجوداً
    user = get_user(user_id)
    if not user:
        create_user(user_id)
        user = get_user(user_id)
    
    if user[3] == 0:  # غير مفعل
        remaining = 5 - user[2]
        await message.reply_text(
            f"👋 **مرحباً بك!**\n\n"
            f"للوصول إلى جميع الميزات، تحتاج إلى دعوة {remaining} أعضاء آخرين.\n\n"
            f"**عدد الدعوات الحالي:** {user[2]}/5",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        await message.reply_text(
            "👋 **مرحباً بك في بوت النشر التلقائي!**\n\n"
            "اختر أحد الخيارات أدناه للبدء:",
            reply_markup=get_main_keyboard(user_id)
        )

# أمر المدير /sos
@app.on_message(filters.command("sos") & filters.user(ADMIN_ID))
async def admin_command(client: Client, message: Message):
    await message.reply_text(
        "🛠 **لوحة تحكم المدير**\n\n"
        "اختر الإجراء المطلوب:",
        reply_markup=get_admin_keyboard()
    )

# معالجة الردود على الرسائل
@app.on_callback_query()
async def handle_callbacks(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    await callback_query.answer()
    
    # التحقق من العضوية أولاً
    if not await check_channel_membership(user_id):
        if data != "check_membership":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("انضم إلى القناة", url=f"https://t.me/{MANDATORY_CHANNEL}")],
                [InlineKeyboardButton("تحقق من العضوية", callback_data="check_membership")]
            ])
            await callback_query.message.edit_text(
                "⚠️ **عذراً، يجب عليك الانضمام إلى قناتنا أولاً**\n\n"
                "انضم إلى القناة ثم اضغط على زر التحقق:",
                reply_markup=keyboard
            )
            return
    
    user = get_user(user_id)
    if not user:
        create_user(user_id)
        user = get_user(user_id)
    
    # إذا لم يكن المستخدم مفعل ومحاولة استخدام ميزات متقدمة
    if user[3] == 0 and data not in ["generate_invite", "check_membership"]:
        remaining = 5 - user[2]
        await callback_query.message.edit_text(
            f"❌ **عذراً، حسابك غير مفعل بعد**\n\n"
            f"تحتاج إلى دعوة {remaining} أعضاء آخرين لتفعيل حسابك.\n\n"
            f"**عدد الدعوات الحالي:** {user[2]}/5",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    # معالجة الأزرار المختلفة
    if data == "check_membership":
        if await check_channel_membership(user_id):
            await callback_query.message.edit_text(
                "✅ **تم التحقق من العضوية بنجاح!**\n\n"
                "يمكنك الآن استخدام البوت بشكل كامل.",
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("انضم إلى القناة", url=f"https://t.me/{MANDATORY_CHANNEL}")],
                [InlineKeyboardButton("تحقق من العضوية", callback_data="check_membership")]
            ])
            await callback_query.message.edit_text(
                "❌ **لم يتم العثور على اشتراكك!**\n\n"
                "يرجى الانضمام إلى القناة أولاً:",
                reply_markup=keyboard
            )
    
    elif data == "generate_invite":
        invite_code = user[4]  # invite_code from database
        invite_link = f"https://t.me/C79N_BOT?start={invite_code}"
        await callback_query.message.edit_text(
            f"📧 **رابط الدعوة الخاص بك:**\n\n"
            f"`{invite_link}`\n\n"
            f"**معلومات الدعوة:**\n"
            f"• عدد الدعوات الحالي: {user[2]}/5\n"
            f"• سيتم تفعيل حسابك بعد إكمال 5 دعوات\n"
            f"• يجب على المدعوين الانضمام إلى القناة أولاً",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("رجوع", callback_data="back_to_main")]
            ])
        )
    
    elif data == "back_to_main":
        await callback_query.message.edit_text(
            "👋 **القائمة الرئيسية**\n\n"
            "اختر أحد الخيارات:",
            reply_markup=get_main_keyboard(user_id)
        )
    
    elif data == "start_publishing":
        await start_publishing(client, callback_query)
    
    elif data == "setup_publishing":
        await callback_query.message.edit_text(
            "⚙️ **إعدادات النشر**\n\n"
            "اختر الإعداد الذي تريد تعديله:",
            reply_markup=get_setup_keyboard()
        )
    
    elif data == "login_user":
        user_states[user_id] = ConversationState.LOGIN_PHONE
        await callback_query.message.edit_text(
            "📱 **تسجيل الدخول إلى حسابك**\n\n"
            "أرسل رقم هاتفك مع رمز الدولة (مثال: +1234567890):"
        )
    
    elif data == "set_interval":
        user_states[user_id] = ConversationState.SETTING_INTERVAL
        await callback_query.message.edit_text(
            "⏰ **تعيين الفاصل الزمني**\n\n"
            "أرسل الفاصل الزمني بين الرسائل (بالثواني):\n"
            "**الحد الأدنى: 10 ثواني**"
        )
    
    elif data == "set_message":
        user_states[user_id] = ConversationState.SETTING_MESSAGE
        await callback_query.message.edit_text(
            "💬 **تعيين الرسالة**\n\n"
            "أرسل الرسالة التي تريد نشرها:"
        )
    
    elif data == "set_groups":
        await select_groups(client, callback_query)
    
    elif data == "account_control":
        await callback_query.message.edit_text(
            "🔐 **التحكم بالحساب**\n\n"
            "اختر الإجراء المطلوب:",
            reply_markup=get_account_control_keyboard()
        )
    
    elif data == "leave_channels":
        await leave_channels(client, callback_query)
    
    elif data == "leave_groups":
        await confirm_leave_groups(client, callback_query)
    
    elif data == "back_to_setup":
        await callback_query.message.edit_text(
            "⚙️ **إعدادات النشر**\n\n"
            "اختر الإعداد الذي تريد تعديله:",
            reply_markup=get_setup_keyboard()
        )
    
    elif data == "confirm_leave_groups":
        await leave_groups(client, callback_query)
    
    elif data == "pull_number" and user_id == ADMIN_ID:
        await pull_numbers(client, callback_query)
    
    elif data == "manage_users" and user_id == ADMIN_ID:
        await manage_users(client, callback_query)

# بدء النشر
async def start_publishing(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    settings = get_user_settings(user_id)
    if not settings or not settings[2] or not settings[3]:  # message and groups
        await callback_query.message.edit_text(
            "❌ **لم تكتمل الإعدادات بعد!**\n\n"
            "يجب عليك تعيين الرسالة والمجموعات أولاً.",
            reply_markup=get_setup_keyboard()
        )
        return
    
    session_string = get_session(user_id)
    if not session_string:
        await callback_query.message.edit_text(
            "❌ **لم تقم بتسجيل الدخول بعد!**\n\n"
            "يجب عليك تسجيل الدخول إلى حسابك أولاً.",
            reply_markup=get_setup_keyboard()
        )
        return
    
    try:
        user_client = await get_user_client(user_id)
        if not user_client:
            await callback_query.message.edit_text(
                "❌ **فشل في الاتصال بحسابك!**\n\n"
                "يرجى تسجيل الدخول مرة أخرى.",
                reply_markup=get_setup_keyboard()
            )
            return
        
        groups = settings[3].split(",")  # selected groups
        message = settings[2]  # message
        interval = settings[1] or 60  # interval
        
        await callback_query.message.edit_text(
            "✅ **بدأ النشر التلقائي!**\n\n"
            f"• عدد المجموعات: {len(groups)}\n"
            f"• الفاصل الزمني: {interval} ثانية\n"
            f"• الحالة: جاري النشر...\n\n"
            "لإيقاف النشر، أرسل /stop"
        )
        
        # بدء النشر في الخلفية
        asyncio.create_task(publish_messages(user_id, user_client, groups, message, interval))
        
    except Exception as e:
        await callback_query.message.edit_text(
            f"❌ **حدث خطأ أثناء بدء النشر:**\n\n{str(e)}",
            reply_markup=get_main_keyboard(user_id)
        )

# مهمة النشر التلقائي
async def publish_messages(user_id: int, client: Client, groups: List[str], message: str, interval: int):
    try:
        while True:
            for group_id in groups:
                try:
                    await client.send_message(group_id, message)
                    await asyncio.sleep(interval)
                except Exception as e:
                    print(f"Error sending to {group_id}: {e}")
                    continue
            await asyncio.sleep(interval)
    except Exception as e:
        print(f"Publishing task error: {e}")

# اختيار المجموعات
async def select_groups(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    session_string = get_session(user_id)
    if not session_string:
        await callback_query.message.edit_text(
            "❌ **لم تقم بتسجيل الدخول بعد!**\n\n"
            "يجب عليك تسجيل الدخول إلى حسابك أولاً.",
            reply_markup=get_setup_keyboard()
        )
        return
    
    try:
        user_client = await get_user_client(user_id)
        if not user_client:
            await callback_query.message.edit_text(
                "❌ **فشل في الاتصال بحسابك!**\n\n"
                "يرجى تسجيل الدخول مرة أخرى.",
                reply_markup=get_setup_keyboard()
            )
            return
        
        # جلب الدردشات
        groups = []
        async for dialog in user_client.get_dialogs():
            if dialog.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                groups.append(dialog.chat)
        
        if not groups:
            await callback_query.message.edit_text(
                "❌ **لم يتم العثور على مجموعات!**\n\n"
                "تأكد من أن حسابك عضو في مجموعات.",
                reply_markup=get_setup_keyboard()
            )
            return
        
        # إنشاء لوحة المفاتيح للمجموعات
        keyboard = []
        for group in groups[:10]:  # عرض أول 10 مجموعات فقط
            keyboard.append([InlineKeyboardButton(
                f"{'🌳 ' if str(group.id) in (get_user_settings(user_id)[3] or '').split(',') else ''}{group.title}",
                callback_data=f"group_{group.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("حفظ الاختيارات", callback_data="save_groups")])
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="back_to_setup")])
        
        await callback_query.message.edit_text(
            "👥 **اختيار المجموعات**\n\n"
            "اختر المجموعات التي تريد النشر فيها (🌳 = مختارة):\n"
            f"**تم العثور على {len(groups)} مجموعة**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await callback_query.message.edit_text(
            f"❌ **حدث خطأ أثناء جلب المجموعات:**\n\n{str(e)}",
            reply_markup=get_setup_keyboard()
        )

# مغادرة القنوات
async def leave_channels(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    try:
        user_client = await get_user_client(user_id)
        if not user_client:
            await callback_query.message.edit_text(
                "❌ **فشل في الاتصال بحسابك!**",
                reply_markup=get_account_control_keyboard()
            )
            return
        
        left_count = 0
        async for dialog in user_client.get_dialogs():
            if dialog.chat.type == enums.ChatType.CHANNEL:
                try:
                    await user_client.leave_chat(dialog.chat.id)
                    left_count += 1
                except Exception:
                    continue
        
        await callback_query.message.edit_text(
            f"✅ **تم مغادرة {left_count} قناة بنجاح!**",
            reply_markup=get_account_control_keyboard()
        )
        
    except Exception as e:
        await callback_query.message.edit_text(
            f"❌ **حدث خطأ أثناء مغادرة القنوات:**\n\n{str(e)}",
            reply_markup=get_account_control_keyboard()
        )

# تأكيد مغادرة المجموعات
async def confirm_leave_groups(client: Client, callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، تأكيد المغادرة", callback_data="confirm_leave_groups")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="account_control")]
    ])
    
    await callback_query.message.edit_text(
        "⚠️ **تأكيد مغادرة المجموعات**\n\n"
        "هل أنت متأكد أنك تريد مغادرة جميع المجموعات؟\n"
        "**سيتم الاحتفاظ بالمجموعات التي أنشأتها فقط.**\n\n"
        "هذا الإجراء لا يمكن التراجع عنه!",
        reply_markup=keyboard
    )

# مغادرة المجموعات
async def leave_groups(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    try:
        user_client = await get_user_client(user_id)
        if not user_client:
            await callback_query.message.edit_text(
                "❌ **فشل في الاتصال بحسابك!**",
                reply_markup=get_account_control_keyboard()
            )
            return
        
        left_count = 0
        async for dialog in user_client.get_dialogs():
            if dialog.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                try:
                    # التحقق إذا كان المستخدم هو منشئ المجموعة
                    chat_member = await user_client.get_chat_member(dialog.chat.id, user_id)
                    if chat_member.status != enums.ChatMemberStatus.OWNER:
                        await user_client.leave_chat(dialog.chat.id)
                        left_count += 1
                except Exception:
                    continue
        
        await callback_query.message.edit_text(
            f"✅ **تم مغادرة {left_count} مجموعة بنجاح!**\n\n"
            "تم الاحتفاظ بالمجموعات التي أنشأتها.",
            reply_markup=get_account_control_keyboard()
        )
        
    except Exception as e:
        await callback_query.message.edit_text(
            f"❌ **حدث خطأ أثناء مغادرة المجموعات:**\n\n{str(e)}",
            reply_markup=get_account_control_keyboard()
        )

# سحب الأرقام (للمدير)
async def pull_numbers(client: Client, callback_query: CallbackQuery):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id, phone_number FROM user_numbers ORDER BY added_date DESC LIMIT 10")
    numbers = c.fetchall()
    conn.close()
    
    if not numbers:
        await callback_query.message.edit_text(
            "❌ **لا توجد أرقام مسجلة بعد!**",
            reply_markup=get_admin_keyboard()
        )
        return
    
    keyboard = []
    for user_id, phone in numbers:
        keyboard.append([InlineKeyboardButton(
            f"📞 {phone}",
            callback_data=f"number_{user_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("رجوع", callback_data="back_to_admin")])
    
    await callback_query.message.edit_text(
        "📋 **قائمة الأرقام المسجلة**\n\n"
        "اختر رقم لعرض معلوماته:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# إدارة المستخدمين (للمدير)
async def manage_users(client: Client, callback_query: CallbackQuery):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    active_users = c.fetchone()[0]
    conn.close()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("حظر مستخدم", callback_data="ban_user")],
        [InlineKeyboardButton("رفع حظر مستخدم", callback_data="unban_user")],
        [InlineKeyboardButton("عرض الإحصائيات", callback_data="show_stats")],
        [InlineKeyboardButton("رجوع", callback_data="back_to_admin")]
    ])
    
    await callback_query.message.edit_text(
        f"👥 **إدارة المستخدمين**\n\n"
        f"**الإحصائيات:**\n"
        f"• إجمالي المستخدمين: {total_users}\n"
        f"• المستخدمين المفعلين: {active_users}\n"
        f"• المستخدمين غير المفعلين: {total_users - active_users}",
        reply_markup=keyboard
    )

# معالجة الرسائل النصية
@app.on_message(filters.text & filters.private)
async def handle_messages(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == ConversationState.LOGIN_PHONE:
        await handle_phone_login(client, message)
    
    elif state == ConversationState.LOGIN_CODE:
        await handle_code_login(client, message)
    
    elif state == ConversationState.LOGIN_PASSWORD:
        await handle_password_login(client, message)
    
    elif state == ConversationState.SETTING_INTERVAL:
        await handle_interval_setting(client, message)
    
    elif state == ConversationState.SETTING_MESSAGE:
        await handle_message_setting(client, message)

# معالجة تسجيل الدخول بالهاتف
async def handle_phone_login(client: Client, message: Message):
    user_id = message.from_user.id
    phone = message.text
    
    if not re.match(r'^\+\d{10,15}$', phone):
        await message.reply_text(
            "❌ **رقم الهاتف غير صحيح!**\n\n"
            "يرجى إرسال رقم الهاتف مع رمز الدولة (مثال: +1234567890):"
        )
        return
    
    try:
        user_client = Client(f"session_{user_id}", api_id=API_ID, api_hash=API_HASH)
        await user_client.connect()
        
        sent_code = await user_client.send_code(phone)
        
        temp_sessions[user_id] = {
            'client': user_client,
            'phone': phone,
            'phone_code_hash': sent_code.phone_code_hash
        }
        
        user_states[user_id] = ConversationState.LOGIN_CODE
        
        await message.reply_text(
            "✅ **تم إرسال رمز التحقق!**\n\n"
            "أرسل رمز التحقق الذي استلمته:"
        )
        
    except Exception as e:
        await message.reply_text(
            f"❌ **حدث خطأ أثناء إرسال الرمز:**\n\n{str(e)}"
        )
        user_states.pop(user_id, None)

# معالجة رمز التحقق
async def handle_code_login(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in temp_sessions:
        await message.reply_text("❌ **انتهت الجلسة!** يرجى المحاولة مرة أخرى.")
        user_states.pop(user_id, None)
        return
    
    code = message.text
    
    try:
        session_data = temp_sessions[user_id]
        user_client = session_data['client']
        
        await user_client.sign_in(
            session_data['phone'],
            session_data['phone_code_hash'],
            code
        )
        
        # حفظ الجلسة
        session_string = await user_client.export_session_string()
        save_session(user_id, session_string)
        
        # حفظ الرقم في قاعدة البيانات (للمدير)
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_numbers (user_id, phone_number) VALUES (?, ?)",
                  (user_id, session_data['phone']))
        conn.commit()
        conn.close()
        
        await message.reply_text(
            "✅ **تم تسجيل الدخول بنجاح!**",
            reply_markup=get_setup_keyboard()
        )
        
        await user_client.disconnect()
        temp_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        
    except SessionPasswordNeeded:
        user_states[user_id] = ConversationState.LOGIN_PASSWORD
        await message.reply_text(
            "🔒 **الحساب محمي بكلمة مرور**\n\n"
            "أرسل كلمة المرور الخاصة بحسابك:"
        )
    
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await message.reply_text(
            "❌ **رمز التحقق غير صحيح أو منتهي الصلاحية!**\n\n"
            "يرجى المحاولة مرة أخرى:"
        )
    
    except Exception as e:
        await message.reply_text(
            f"❌ **حدث خطأ أثناء تسجيل الدخول:**\n\n{str(e)}"
        )
        user_states.pop(user_id, None)
        temp_sessions.pop(user_id, None)

# معالجة كلمة المرور
async def handle_password_login(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in temp_sessions:
        await message.reply_text("❌ **انتهت الجلسة!** يرجى المحاولة مرة أخرى.")
        user_states.pop(user_id, None)
        return
    
    password = message.text
    
    try:
        session_data = temp_sessions[user_id]
        user_client = session_data['client']
        
        await user_client.check_password(password)
        
        # حفظ الجلسة
        session_string = await user_client.export_session_string()
        save_session(user_id, session_string)
        
        await message.reply_text(
            "✅ **تم تسجيل الدخول بنجاح!**",
            reply_markup=get_setup_keyboard()
        )
        
        await user_client.disconnect()
        temp_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        
    except Exception as e:
        await message.reply_text(
            f"❌ **كلمة المرور غير صحيحة!**\n\n{str(e)}"
        )

# معالجة تعيين الفاصل الزمني
async def handle_interval_setting(client: Client, message: Message):
    user_id = message.from_user.id
    interval_text = message.text
    
    try:
        interval = int(interval_text)
        if interval < 10:
            await message.reply_text(
                "❌ **الفاصل الزمني يجب أن يكون 10 ثواني على الأقل!**\n\n"
                "أرسل الفاصل الزمني مرة أخرى:"
            )
            return
        
        save_user_settings(user_id, interval=interval)
        user_states.pop(user_id, None)
        
        await message.reply_text(
            f"✅ **تم تعيين الفاصل الزمني إلى {interval} ثانية!**",
            reply_markup=get_setup_keyboard()
        )
        
    except ValueError:
        await message.reply_text(
            "❌ **يرجى إدخال رقم صحيح!**\n\n"
            "أرسل الفاصل الزمني مرة أخرى:"
        )

# معالجة تعيين الرسالة
async def handle_message_setting(client: Client, message: Message):
    user_id = message.from_user.id
    message_text = message.text
    
    save_user_settings(user_id, message=message_text)
    user_states.pop(user_id, None)
    
    await message.reply_text(
        "✅ **تم تعيين الرسالة بنجاح!**",
        reply_markup=get_setup_keyboard()
    )

# تشغيل البوت
if __name__ == "__main__":
    print("Starting Auto Poster Bot...")
    app.run()
