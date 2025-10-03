import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
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
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# إعدادات البوت
BOT_TOKEN = "8398354970:AAEZ2KASsMsTIYZDSRAX5DTzzWUiCrvW9zo"
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
ADMIN_ID = 6689435577

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# حالات المحادثة
CHOOSING, TYPING_MESSAGE, AUTH_CODE, AUTH_PHONE = range(4)

# قاعدة البيانات
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            session_string TEXT,
            is_banned BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # جدول العمليات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            groups TEXT,
            message TEXT,
            interval INTEGER,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

class TelegramAutoPoster:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.scheduler = AsyncIOScheduler()
        self.user_clients: Dict[int, TelegramClient] = {}
        self.setup_handlers()
        
    def setup_handlers(self):
        # القائمة الرئيسية
        self.application.add_handler(CommandHandler("start", self.main_menu))
        self.application.add_handler(CommandHandler("sos", self.admin_menu))
        
        # معالجات الأزرار
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern="^(start_publish|active_operations|updates|setup|back|pause|resume|delete|stats|register_account|target_groups|interval|message_text|set_groups|set_interval|set_message|confirm_start|phone_submit|code_submit|admin_numbers|admin_users|ban_user|unban_user|prev_page|next_page)$"))
        
        # معالجات الرسائل
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_auth, pattern="^register_account$")],
            states={
                AUTH_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_phone)],
                AUTH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_code)],
                TYPING_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_message)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        self.application.add_handler(conv_handler)
        
        # معالج الرسائل العامة
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            ["بدء عملية النشر"],
            ["العمليات النشطة", "التحديثات"],
            ["تهيئة عملية النشر"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "مرحباً! اختر من القائمة:",
            reply_markup=reply_markup
        )
    
    async def admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية الوصول لهذا الأمر")
            return
            
        keyboard = [
            [InlineKeyboardButton("سحب رقم", callback_data="admin_numbers")],
            [InlineKeyboardButton("إدارة المستخدمين", callback_data="admin_users")],
            [InlineKeyboardButton("رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "لوحة المدير:",
            reply_markup=reply_markup
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "start_publish":
            await self.start_publishing(update, context)
        elif data == "active_operations":
            await self.show_active_operations(update, context)
        elif data == "updates":
            await self.show_updates(update, context)
        elif data == "setup":
            await self.show_setup_menu(update, context)
        elif data == "back":
            await self.main_menu_callback(update, context)
        elif data == "register_account":
            await self.start_auth(update, context)
        elif data == "target_groups":
            await self.show_groups_selection(update, context)
        elif data == "interval":
            await self.show_interval_selection(update, context)
        elif data == "message_text":
            await self.request_message(update, context)
        elif data == "set_interval":
            await self.set_interval(update, context)
        elif data == "confirm_start":
            await self.confirm_start_publishing(update, context)
    
    async def start_publishing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # التحقق من وجود تهيئة
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            await update.callback_query.edit_message_text(
                "❌ يجب تهيئة عملية النشر أولاً (تسجيل حساب + تعيين المجموعات + الرسالة + الفاصل الزمني)"
            )
            conn.close()
            return
        
        cursor.execute("SELECT * FROM processes WHERE user_id = ? AND status = 'active'", (user_id,))
        active_process = cursor.fetchone()
        conn.close()
        
        if active_process:
            await update.callback_query.edit_message_text("✅ لديك عملية نشر نشطة بالفعل")
        else:
            await update.callback_query.edit_message_text("🚀 بدء عملية النشر...")
            # بدء عملية النشر المجدولة
            await self.start_scheduled_posting(user_id)
    
    async def show_active_operations(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processes WHERE user_id = ?", (user_id,))
        processes = cursor.fetchall()
        conn.close()
        
        if not processes:
            await update.callback_query.edit_message_text("❌ لا توجد عمليات نشطة")
            return
        
        keyboard = []
        for process in processes:
            process_id, _, groups, _, interval, status, _ = process
            keyboard.append([InlineKeyboardButton(
                f"المجموعات ({len(eval(groups))}) - {status}", 
                callback_data=f"process_{process_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "العمليات النشطة:",
            reply_markup=reply_markup
        )
    
    async def show_updates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("قناة الاشتراك الإجباري", url="https://t.me/iIl337")],
            [InlineKeyboardButton("رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "التحديثات والإشتراك الإجباري:",
            reply_markup=reply_markup
        )
    
    async def show_setup_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("تسجيل حساب", callback_data="register_account")],
            [InlineKeyboardButton("المجموعة الهدف", callback_data="target_groups")],
            [InlineKeyboardButton("الفاصل الزمني", callback_data="interval")],
            [InlineKeyboardButton("رسالة النشر", callback_data="message_text")],
            [InlineKeyboardButton("بدء النشر", callback_data="confirm_start")],
            [InlineKeyboardButton("رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "تهيئة عملية النشر:",
            reply_markup=reply_markup
        )
    
    async def start_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.edit_message_text(
            "أرسل رقم هاتفك مع رمز الدولة (مثال: +201234567890):"
        )
        return AUTH_PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        phone = update.message.text
        context.user_data['phone'] = phone
        
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            
            await client.send_code_request(phone)
            context.user_data['client'] = client
            
            await update.message.reply_text("أرسل كود التحقق الذي استلمته:")
            return AUTH_CODE
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
            return ConversationHandler.END
    
    async def get_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        code = update.message.text
        phone = context.user_data['phone']
        client = context.user_data['client']
        
        try:
            await client.sign_in(phone, code)
            session_string = client.session.save()
            
            # حفظ في قاعدة البيانات
            conn = sqlite3.connect('bot.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO users (user_id, phone, session_string) VALUES (?, ?, ?)",
                (update.effective_user.id, phone, session_string)
            )
            conn.commit()
            conn.close()
            
            await update.message.reply_text("✅ تم تسجيل الحساب بنجاح!")
            await client.disconnect()
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في التسجيل: {str(e)}")
        
        return ConversationHandler.END
    
    async def show_groups_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # جلب المجموعات من التليثون
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT session_string FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            await update.callback_query.edit_message_text("❌ يجب تسجيل حساب أولاً")
            return
        
        try:
            client = TelegramClient(StringSession(user[0]), API_ID, API_HASH)
            await client.connect()
            
            groups = []
            async for dialog in client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    groups.append({
                        'id': dialog.id,
                        'name': dialog.name,
                        'type': 'channel' if dialog.is_channel else 'group'
                    })
            
            await client.disconnect()
            
            # حفظ المجموعات مؤقتاً
            context.user_data['available_groups'] = groups
            context.user_data['selected_groups'] = []
            
            await self.display_groups_page(update, context)
            
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ خطأ في جلب المجموعات: {str(e)}")
    
    async def display_groups_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        groups = context.user_data['available_groups']
        selected_groups = context.user_data['selected_groups']
        page = context.user_data.get('groups_page', 0)
        items_per_page = 8
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_groups = groups[start_idx:end_idx]
        
        keyboard = []
        for group in page_groups:
            is_selected = group['id'] in selected_groups
            emoji = "✅" if is_selected else "◻️"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {group['name']}", 
                callback_data=f"toggle_group_{group['id']}"
            )])
        
        # أزرار التنقل
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("السابق", callback_data="prev_page"))
        if end_idx < len(groups):
            nav_buttons.append(InlineKeyboardButton("التالي", callback_data="next_page"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("تعيين", callback_data="set_groups")])
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="setup")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            f"اختر المجموعات (الصفحة {page + 1}):",
            reply_markup=reply_markup
        )
    
    async def show_interval_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("2 دقائق", callback_data="interval_2")],
            [InlineKeyboardButton("5 دقائق", callback_data="interval_5")],
            [InlineKeyboardButton("10 دقائق", callback_data="interval_10")],
            [InlineKeyboardButton("20 دقيقة", callback_data="interval_20")],
            [InlineKeyboardButton("1 ساعة", callback_data="interval_60")],
            [InlineKeyboardButton("1 يوم", callback_data="interval_1440")],
            [InlineKeyboardButton("2 يوم", callback_data="interval_2880")],
            [InlineKeyboardButton("رجوع", callback_data="setup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "اختر الفاصل الزمني بين الرسائل:",
            reply_markup=reply_markup
        )
    
    async def set_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        interval = int(update.callback_query.data.split('_')[1])
        context.user_data['interval'] = interval
        
        intervals = {
            2: "2 دقائق",
            5: "5 دقائق", 
            10: "10 دقائق",
            20: "20 دقيقة",
            60: "1 ساعة",
            1440: "1 يوم",
            2880: "2 يوم"
        }
        
        await update.callback_query.edit_message_text(
            f"✅ تم تعيين الفاصل الزمني: {intervals[interval]}"
        )
    
    async def request_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.edit_message_text(
            "أرسل رسالة النشر التي تريد إرسالها:"
        )
        return TYPING_MESSAGE
    
    async def save_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message.text
        context.user_data['message'] = message
        
        await update.message.reply_text("✅ تم حفظ رسالة النشر")
        return ConversationHandler.END
    
    async def confirm_start_publishing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # التحقق من اكتمال التهيئة
        required = ['selected_groups', 'interval', 'message']
        missing = [item for item in required if item not in context.user_data]
        
        if missing:
            await update.callback_query.edit_message_text(
                f"❌ يجب إكمال التهيئة أولاً: {', '.join(missing)}"
            )
            return
        
        # حفظ العملية في قاعدة البيانات
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO processes (user_id, groups, message, interval, status) VALUES (?, ?, ?, ?, ?)",
            (user_id, str(context.user_data['selected_groups']), context.user_data['message'], 
             context.user_data['interval'], 'active')
        )
        conn.commit()
        conn.close()
        
        await update.callback_query.edit_message_text(
            "✅ تم تهيئة عملية النشر بنجاح! يمكنك الآن البدء بالنشر من القائمة الرئيسية."
        )
    
    async def start_scheduled_posting(self, user_id: int):
        # بدء النشر المجدول
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processes WHERE user_id = ? AND status = 'active'", (user_id,))
        process = cursor.fetchone()
        cursor.execute("SELECT session_string FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not process or not user:
            return
        
        process_id, _, groups_str, message, interval, status, _ = process
        groups = eval(groups_str)
        session_string = user[0]
        
        # إضافة المهمة للمجدول
        self.scheduler.add_job(
            self.send_scheduled_message,
            'interval',
            minutes=interval,
            args=[user_id, process_id, groups, message, session_string],
            id=f"process_{process_id}"
        )
    
    async def send_scheduled_message(self, user_id: int, process_id: int, groups: List, message: str, session_string: str):
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            for group_id in groups:
                try:
                    await client.send_message(group_id, message)
                    await asyncio.sleep(2)  # فاصل بين الرسائل
                except Exception as e:
                    print(f"Error sending to group {group_id}: {e}")
            
            await client.disconnect()
        except Exception as e:
            print(f"Error in scheduled posting: {e}")
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            ["بدء عملية النشر"],
            ["العمليات النشطة", "التحديثات"],
            ["تهيئة عملية النشر"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.callback_query.edit_message_text(
            "مرحباً! اختر من القائمة:",
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        
        if text == "بدء عملية النشر":
            await self.start_publishing_message(update, context)
        elif text == "العمليات النشطة":
            await self.active_operations_message(update, context)
        elif text == "التحديثات":
            await self.updates_message(update, context)
        elif text == "تهيئة عملية النشر":
            await self.setup_message(update, context)
    
    async def start_publishing_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processes WHERE user_id = ? AND status = 'active'", (user_id,))
        active_process = cursor.fetchone()
        conn.close()
        
        if active_process:
            await update.message.reply_text("✅ لديك عملية نشر نشطة بالفعل")
        else:
            await update.message.reply_text("🚀 بدء عملية النشر...")
            await self.start_scheduled_posting(user_id)
    
    async def active_operations_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processes WHERE user_id = ?", (user_id,))
        processes = cursor.fetchall()
        conn.close()
        
        if not processes:
            await update.message.reply_text("❌ لا توجد عمليات نشطة")
            return
        
        keyboard = []
        for process in processes:
            process_id, _, groups, _, interval, status, _ = process
            keyboard.append([InlineKeyboardButton(
                f"المجموعات ({len(eval(groups))}) - {status}", 
                callback_data=f"process_{process_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("رجوع", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "العمليات النشطة:",
            reply_markup=reply_markup
        )
    
    async def updates_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("قناة الاشتراك الإجباري", url="https://t.me/iIl337")],
            [InlineKeyboardButton("رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "التحديثات والإشتراك الإجباري:",
            reply_markup=reply_markup
        )
    
    async def setup_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("تسجيل حساب", callback_data="register_account")],
            [InlineKeyboardButton("المجموعة الهدف", callback_data="target_groups")],
            [InlineKeyboardButton("الفاصل الزمني", callback_data="interval")],
            [InlineKeyboardButton("رسالة النشر", callback_data="message_text")],
            [InlineKeyboardButton("بدء النشر", callback_data="confirm_start")],
            [InlineKeyboardButton("رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "تهيئة عملية النشر:",
            reply_markup=reply_markup
        )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("تم الإلغاء")
        return ConversationHandler.END
    
    def run(self):
        self.scheduler.start()
        self.application.run_polling()

if __name__ == "__main__":
    bot = TelegramAutoPoster()
    bot.run()
