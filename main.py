import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
from collections import defaultdict

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    ConversationHandler
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# إعدادات API
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
BOT_TOKEN = "8052900952:AAEvZKao98ibPDlUqxBVcj6In1YOa4cbW18"

# تعريف الحالات للمحادثة
SETUP_ACCOUNT, SETUP_GROUPS, SETUP_INTERVAL, SETUP_MESSAGE = range(4)

# تخزين البيانات
user_sessions = {}
user_configs = {}
active_processes = {}
user_stats = defaultdict(lambda: {
    'messages_sent': 0,
    'last_sent': None,
    'errors': 0
})

# إدارة الحسابات
accounts_db = {}
banned_users = set()
admin_id = 6689435577

# الفواصل الزمنية
INTERVALS = {
    "2 دقائق": 2,
    "5 دقائق": 5,
    "10 دقائق": 10,
    "20 دقيقة": 20,
    "ساعة": 60,
    "يوم": 1440,
    "يومين": 2880
}

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class TelegramPoster:
    def __init__(self, user_id):
        self.user_id = user_id
        self.client = None
        self.session_string = None
        self.is_connected = False
        
    async def create_session(self, phone, code, password=None):
        try:
            self.client = TelegramClient(
                StringSession(), 
                API_ID, 
                API_HASH
            )
            
            await self.client.start(
                phone=phone,
                code=code,
                password=password
            )
            
            self.session_string = self.client.session.save()
            self.is_connected = True
            return True
        except SessionPasswordNeededError:
            return "password"
        except Exception as e:
            return str(e)
    
    async def send_message(self, group_entity, message):
        try:
            await self.client.send_message(group_entity, message)
            return True
        except Exception as e:
            return str(e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in banned_users:
        await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
        return
    
    keyboard = [
        [KeyboardButton("1- بدء عملية النشر")],
        [KeyboardButton("2- العمليات النشطة")],
        [KeyboardButton("3- التحديثات")],
        [KeyboardButton("4- تهيئة عملية النشر")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "مرحباً! 👋\nاختر من القائمة:",
        reply_markup=reply_markup
    )

async def handle_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "1- بدء عملية النشر":
        await start_posting_process(update, context)
    elif text == "2- العمليات النشطة":
        await show_active_processes(update, context)
    elif text == "3- التحديثات":
        await show_updates(update, context)
    elif text == "4- تهيئة عملية النشر":
        await setup_posting_process(update, context)

async def start_posting_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_configs or not user_configs[user_id].get('is_complete', False):
        await update.message.reply_text(
            "❌ يجب تهيئة عملية النشر أولاً من الخيار 4"
        )
        return
    
    config = user_configs[user_id]
    
    if user_id in active_processes:
        await update.message.reply_text("⚠️ لديك عملية نشر نشطة بالفعل")
        return
    
    # بدء عملية النشر
    active_processes[user_id] = {
        'config': config,
        'is_paused': False,
        'start_time': datetime.now()
    }
    
    asyncio.create_task(run_posting_process(user_id, config))
    
    await update.message.reply_text("✅ بدأت عملية النشر بنجاح!")

async def run_posting_process(user_id: int, config: dict):
    poster = user_sessions.get(user_id)
    if not poster or not poster.is_connected:
        return
    
    while user_id in active_processes and not active_processes[user_id]['is_paused']:
        try:
            for group in config['groups']:
                if user_id not in active_processes or active_processes[user_id]['is_paused']:
                    break
                    
                result = await poster.send_message(group, config['message'])
                if result is True:
                    user_stats[user_id]['messages_sent'] += 1
                    user_stats[user_id]['last_sent'] = datetime.now()
                else:
                    user_stats[user_id]['errors'] += 1
                
                # انتظار الفاصل الزمني
                interval_minutes = INTERVALS[config['interval']]
                await asyncio.sleep(interval_minutes * 60)
                
        except Exception as e:
            user_stats[user_id]['errors'] += 1
            await asyncio.sleep(60)

async def show_active_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in active_processes:
        await update.message.reply_text("❌ لا توجد عمليات نشطة")
        return
    
    processes = []
    for uid, process in active_processes.items():
        if uid == user_id:
            config = process['config']
            status = "⏸ متوقف" if process['is_paused'] else "▶️ نشط"
            processes.append(f"المجموعات: {len(config['groups'])} | الحالة: {status}")
    
    if not processes:
        await update.message.reply_text("❌ لا توجد عمليات نشطة")
        return
    
    keyboard = [[InlineKeyboardButton("إدارة العمليات", callback_data="manage_processes")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "\n".join(processes),
        reply_markup=reply_markup
    )

async def show_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("قناة التحديثات", url="https://t.me/iIl337")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📢 آخر التحديثات متوفرة في قناتنا:",
        reply_markup=reply_markup
    )

async def setup_posting_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['setup_stage'] = 'start'
    
    keyboard = [
        [InlineKeyboardButton("تسجيل حساب", callback_data="setup_account")],
        [InlineKeyboardButton("المجموعة الهدف", callback_data="setup_groups")],
        [InlineKeyboardButton("الفاصل الزمني", callback_data="setup_interval")],
        [InlineKeyboardButton("رسالة النشر", callback_data="setup_message")],
        [InlineKeyboardButton("تم التهيئة", callback_data="setup_complete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ تهيئة عملية النشر:\nاختر الخيارات اللازمة:",
        reply_markup=reply_markup
    )

async def handle_setup_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "setup_account":
        await query.edit_message_text(
            "📱 إرسال رقم الهاتف مع رمز الدولة (مثال: +1234567890):"
        )
        context.user_data['expecting_phone'] = True
        
    elif data == "setup_groups":
        if user_id not in user_sessions or not user_sessions[user_id].is_connected:
            await query.edit_message_text("❌ يجب تسجيل الحساب أولاً")
            return
        
        await show_user_groups(query, context)
        
    elif data == "setup_interval":
        keyboard = []
        intervals_list = list(INTERVALS.keys())
        
        for i in range(0, len(intervals_list), 2):
            row = []
            for j in range(2):
                if i + j < len(intervals_list):
                    interval = intervals_list[i + j]
                    row.append(InlineKeyboardButton(interval, callback_data=f"interval_{interval}"))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="setup_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏰ اختر الفاصل الزمني بين الرسائل:",
            reply_markup=reply_markup
        )
        
    elif data == "setup_message":
        await query.edit_message_text(
            "📝 إرسال رسالة النشر النصية:"
        )
        context.user_data['expecting_message'] = True
        
    elif data == "setup_complete":
        if await validate_setup(user_id):
            user_configs[user_id]['is_complete'] = True
            await query.edit_message_text("✅ تم تهيئة عملية النشر بنجاح!")
        else:
            await query.edit_message_text("❌ لم تكتمل التهيئة بعد")

async def show_user_groups(query, context):
    user_id = query.from_user.id
    poster = user_sessions.get(user_id)
    
    if not poster or not poster.is_connected:
        await query.edit_message_text("❌ يجب تسجيل الحساب أولاً")
        return
    
    try:
        groups = []
        async for dialog in poster.client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                groups.append(dialog.entity)
        
        context.user_data['user_groups'] = groups
        await display_groups_page(query, context, page=0)
        
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ في جلب المجموعات: {str(e)}")

async def display_groups_page(query, context, page=0):
    groups = context.user_data.get('user_groups', [])
    items_per_page = 8
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    
    keyboard = []
    for group in groups[start_idx:end_idx]:
        group_name = group.title if hasattr(group, 'title') else str(group.id)
        keyboard.append([InlineKeyboardButton(
            group_name, 
            callback_data=f"select_group_{group.id}"
        )])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("السابق", callback_data=f"groups_page_{page-1}"))
    
    if end_idx < len(groups):
        nav_buttons.append(InlineKeyboardButton("التالي", callback_data=f"groups_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton("تعيين المختارة", callback_data="confirm_groups"),
        InlineKeyboardButton("رجوع", callback_data="setup_back")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 اختر المجموعات المستهدفة (الصفحة {page + 1}):",
        reply_markup=reply_markup
    )

async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone = update.message.text
    
    context.user_data['phone'] = phone
    context.user_data['expecting_phone'] = False
    context.user_data['expecting_code'] = True
    
    # إنشاء جلسة جديدة
    if user_id not in user_sessions:
        user_sessions[user_id] = TelegramPoster(user_id)
    
    await update.message.reply_text("🔐 أرسل كود التحقق:")

async def handle_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text
    
    phone = context.user_data.get('phone')
    poster = user_sessions.get(user_id)
    
    if not poster:
        await update.message.reply_text("❌ حدث خطأ، حاول مرة أخرى")
        return
    
    result = await poster.create_session(phone, code)
    
    if result is True:
        await update.message.reply_text("✅ تم تسجيل الحساب بنجاح!")
        user_configs[user_id] = {'account_setup': True}
    elif result == "password":
        context.user_data['expecting_password'] = True
        await update.message.reply_text("🔒 أرسل كلمة المرور ثنائية التحقق:")
    else:
        await update.message.reply_text(f"❌ خطأ في التسجيل: {result}")

async def handle_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    password = update.message.text
    
    phone = context.user_data.get('phone')
    poster = user_sessions.get(user_id)
    
    if not poster:
        await update.message.reply_text("❌ حدث خطأ، حاول مرة أخرى")
        return
    
    # إعادة المحاولة مع كلمة المرور
    # Note: تحتاج إلى تعديل دالة create_session لدعم كلمة المرور

async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text
    
    if user_id not in user_configs:
        user_configs[user_id] = {}
    
    user_configs[user_id]['message'] = message
    context.user_data['expecting_message'] = False
    
    await update.message.reply_text("✅ تم حفظ رسالة النشر!")

async def validate_setup(user_id: int) -> bool:
    config = user_configs.get(user_id, {})
    return all([
        config.get('account_setup', False),
        config.get('groups'),
        config.get('interval'),
        config.get('message')
    ])

# أوامر المدير
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != admin_id:
        await update.message.reply_text("❌ غير مصرح لك بالوصول لهذا الأمر")
        return
    
    keyboard = [
        [InlineKeyboardButton("سحب رقم", callback_data="admin_extract_number")],
        [InlineKeyboardButton("إدارة المستخدمين", callback_data="admin_manage_users")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 لوحة المدير:",
        reply_markup=reply_markup
    )

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if user_id != admin_id:
        return
    
    if data == "admin_extract_numbers":
        await show_user_numbers(query, context)
    elif data == "admin_manage_users":
        await show_user_management(query, context)

async def show_user_numbers(query, context, page=0):
    users = list(user_sessions.keys())
    items_per_page = 8
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    
    keyboard = []
    for user_id in users[start_idx:end_idx]:
        keyboard.append([InlineKeyboardButton(
            f"User {user_id}", 
            callback_data=f"admin_user_{user_id}"
        )])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("السابق", callback_data=f"admin_numbers_page_{page-1}"))
    
    if end_idx < len(users):
        nav_buttons.append(InlineKeyboardButton("التالي", callback_data=f"admin_numbers_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("رجوع", callback_data="admin_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📞 أرقام المستخدمين (الصفحة {page + 1}):",
        reply_markup=reply_markup
    )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # handlers الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sos", admin_panel))
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_main_buttons
    ))
    
    # handler معالجة الرسائل النصية للإدخال
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^\+\d+$'),
        handle_phone_input
    ))
    
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'^\d+$'),
        handle_code_input
    ))
    
    application.add_handler(MessageHandler(
        filters.TEXT,
        handle_message_input
    ))
    
    # handler استدعاءات Inline
    application.add_handler(CallbackQueryHandler(handle_setup_callbacks, pattern="^setup_"))
    application.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_"))
    
    print("🤖 البوت يعمل...")
    application.run_polling()

if __name__ == "__main__":
    main()
