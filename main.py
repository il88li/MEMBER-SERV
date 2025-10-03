import os
import json
import sqlite3
import logging
import asyncio
import threading
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat
from telethon.errors import SessionPasswordNeededError, FloodWaitError

# ============================
# الإعدادات والتكوين
# ============================

BOT_TOKEN = "8398354970:AAEZ2KASsMsTIYZDSRAX5DTzzWUiCrvW9zo"
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
ADMIN_ID = 6689435577
CHANNEL_USERNAME = "iIl337"

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================
# إدارة قاعدة البيانات
# ============================

class DatabaseManager:
    def __init__(self, db_path: str = "auto_poster.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """تهيئة قاعدة البيانات"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # جدول المستخدمين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                session_string TEXT,
                is_banned BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # جدول الإعدادات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                selected_groups TEXT,
                message_text TEXT,
                interval INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # جدول إحصائيات النشر
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posting_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                process_id INTEGER,
                group_id INTEGER,
                message_sent BOOLEAN,
                error_message TEXT,
                posted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (process_id) REFERENCES processes (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        return sqlite3.connect(self.db_path)
    
    # عمليات المستخدمين
    def save_user(self, user_id: int, phone: str, session_string: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, phone, session_string) VALUES (?, ?, ?)",
            (user_id, phone, session_string)
        )
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        conn.close()
        return users
    
    def ban_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = TRUE WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def unban_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = FALSE WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    # عمليات النشر
    def save_process(self, user_id: int, groups: List[int], message: str, interval: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO processes (user_id, groups, message, interval) VALUES (?, ?, ?, ?)",
            (user_id, json.dumps(groups), message, interval)
        )
        process_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return process_id
    
    def get_user_processes(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processes WHERE user_id = ?", (user_id,))
        processes = cursor.fetchall()
        conn.close()
        return processes
    
    def get_process(self, process_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processes WHERE id = ?", (process_id,))
        process = cursor.fetchone()
        conn.close()
        return process
    
    def update_process_status(self, process_id: int, status: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE processes SET status = ? WHERE id = ?", (status, process_id))
        conn.commit()
        conn.close()
    
    # إعدادات المستخدم
    def save_user_settings(self, user_id: int, selected_groups: List[int] = None, 
                          message_text: str = None, interval: int = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # الحصول على الإعدادات الحالية
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        current = cursor.fetchone()
        
        if current:
            # تحديث الإعدادات الحالية
            updates = []
            params = []
            
            if selected_groups is not None:
                updates.append("selected_groups = ?")
                params.append(json.dumps(selected_groups))
            
            if message_text is not None:
                updates.append("message_text = ?")
                params.append(message_text)
            
            if interval is not None:
                updates.append("interval = ?")
                params.append(interval)
            
            if updates:
                params.append(user_id)
                cursor.execute(
                    f"UPDATE user_settings SET {', '.join(updates)} WHERE user_id = ?",
                    params
                )
        else:
            # إدخال جديد
            cursor.execute(
                "INSERT INTO user_settings (user_id, selected_groups, message_text, interval) VALUES (?, ?, ?, ?)",
                (user_id, 
                 json.dumps(selected_groups) if selected_groups else None,
                 message_text,
                 interval)
            )
        
        conn.commit()
        conn.close()
    
    def get_user_settings(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        settings = cursor.fetchone()
        conn.close()
        return settings
    
    # الإحصائيات
    def save_posting_stat(self, user_id: int, process_id: int, group_id: int, 
                         message_sent: bool, error_message: str = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO posting_stats (user_id, process_id, group_id, message_sent, error_message) VALUES (?, ?, ?, ?, ?)",
            (user_id, process_id, group_id, message_sent, error_message)
        )
        conn.commit()
        conn.close()
    
    def get_process_stats(self, process_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total, SUM(message_sent) as successful FROM posting_stats WHERE process_id = ?",
            (process_id,)
        )
        stats = cursor.fetchone()
        conn.close()
        return stats

# ============================
# إدارة Telethon
# ============================

class TelethonManager:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients: Dict[int, TelegramClient] = {}
    
    async def create_client(self, session_string: str = None) -> TelegramClient:
        """إنشاء عميل Telethon"""
        client = TelegramClient(
            StringSession(session_string) if session_string else StringSession(),
            self.api_id,
            self.api_hash
        )
        await client.connect()
        return client
    
    async def get_user_groups(self, session_string: str) -> List[Dict[str, Any]]:
        """الحصول على مجموعات المستخدم"""
        client = None
        try:
            client = await self.create_client(session_string)
            groups = []
            
            async for dialog in client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    entity = dialog.entity
                    groups.append({
                        'id': entity.id,
                        'name': dialog.name,
                        'type': 'channel' if dialog.is_channel else 'group',
                        'participants_count': getattr(entity, 'participants_count', 0)
                    })
            
            return groups
        except Exception as e:
            logger.error(f"Error getting user groups: {e}")
            return []
        finally:
            if client:
                await client.disconnect()
    
    async def send_message_to_groups(self, session_string: str, group_ids: List[int], message: str) -> List[Dict]:
        """إرسال رسالة إلى مجموعات متعددة"""
        client = None
        try:
            client = await self.create_client(session_string)
            results = []
            
            for group_id in group_ids:
                try:
                    await client.send_message(group_id, message)
                    results.append({'group_id': group_id, 'status': 'success'})
                    await asyncio.sleep(2)  # فاصل بين الرسائل
                except FloodWaitError as e:
                    results.append({'group_id': group_id, 'status': 'flood_wait', 'seconds': e.seconds})
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    results.append({'group_id': group_id, 'status': 'error', 'error': str(e)})
            
            return results
        except Exception as e:
            logger.error(f"Error sending messages: {e}")
            return []
        finally:
            if client:
                await client.disconnect()
    
    async def authenticate_user(self, phone: str) -> tuple:
        """بدء عملية المصادقة"""
        client = await self.create_client()
        try:
            sent_code = await client.send_code_request(phone)
            return client, sent_code.phone_code_hash
        except Exception as e:
            await client.disconnect()
            raise e
    
    async def verify_code(self, client: TelegramClient, phone: str, code: str, phone_code_hash: str) -> str:
        """التحقق من الكود واستكمال المصادقة"""
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            session_string = client.session.save()
            return session_string
        except SessionPasswordNeededError:
            raise Exception("الحساب محمي بكلمة مرور. لا يمكن استخدامه.")
        except Exception as e:
            raise e
        finally:
            await client.disconnect()

# ============================
# جدولة المهام
# ============================

class MessageScheduler:
    def __init__(self, db: DatabaseManager, telethon_manager: TelethonManager):
        self.db = db
        self.telethon_manager = telethon_manager
        self.active_processes: Dict[int, bool] = {}
        self.is_running = True
    
    def start_process(self, process_id: int):
        """بدء عملية النشر المجدولة"""
        process = self.db.get_process(process_id)
        if not process:
            return
        
        user_id = process[1]
        groups = json.loads(process[2])
        message = process[3]
        interval = process[4]
        
        user = self.db.get_user(user_id)
        if not user:
            return
        
        session_string = user[2]  # session_string
        
        # بدء العملية في thread منفصل
        self.active_processes[process_id] = True
        thread = threading.Thread(
            target=self._run_scheduling,
            args=(process_id, user_id, groups, message, interval, session_string),
            daemon=True
        )
        thread.start()
    
    def _run_scheduling(self, process_id: int, user_id: int, groups: List[int], 
                       message: str, interval: int, session_string: str):
        """تشغيل النشر المجدول"""
        while self.is_running and self.active_processes.get(process_id, False):
            try:
                # تشغيل Telethon في event loop منفصل
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                results = loop.run_until_complete(
                    self.telethon_manager.send_message_to_groups(session_string, groups, message)
                )
                
                # حفظ الإحصائيات
                for result in results:
                    if result['status'] == 'success':
                        self.db.save_posting_stat(user_id, process_id, result['group_id'], True)
                    else:
                        self.db.save_posting_stat(user_id, process_id, result['group_id'], False, 
                                                result.get('error', 'Unknown error'))
                
                logger.info(f"Process {process_id}: Sent messages to {len(groups)} groups")
                
            except Exception as e:
                logger.error(f"Error in process {process_id}: {e}")
            
            # الانتظار للفاصل الزمني
            for _ in range(interval * 60):  # تحويل الدقائق إلى ثواني
                if not self.is_running or not self.active_processes.get(process_id, False):
                    break
                time.sleep(1)
    
    def stop_process(self, process_id: int):
        """إيقاف عملية النشر"""
        self.active_processes[process_id] = False
    
    def stop_all(self):
        """إيقاف جميع العمليات"""
        self.is_running = False
        self.active_processes.clear()

# ============================
# البوت الرئيسي
# ============================

class TelegramAutoPosterBot:
    def __init__(self):
        self.bot = telebot.TeleBot(BOT_TOKEN)
        self.db = DatabaseManager()
        self.telethon_manager = TelethonManager(API_ID, API_HASH)
        self.scheduler = MessageScheduler(self.db, self.telethon_manager)
        self.user_states = {}  # لتتبع حالة المستخدم
        self.setup_handlers()
    
    def setup_handlers(self):
        """إعداد معالجات الأحداث"""
        
        # الأمر /start
        @self.bot.message_handler(commands=['start'])
        def start_handler(message):
            self.show_main_menu(message.chat.id)
        
        # الأمر /sos (للمدير فقط)
        @self.bot.message_handler(commands=['sos'])
        def sos_handler(message):
            if message.from_user.id == ADMIN_ID:
                self.show_admin_menu(message.chat.id)
            else:
                self.bot.send_message(message.chat.id, "❌ ليس لديك صلاحية الوصول لهذا الأمر")
        
        # معالجة الأزرار الرئيسية
        @self.bot.message_handler(func=lambda message: True)
        def message_handler(message):
            text = message.text
            chat_id = message.chat.id
            
            if text == "بدء عملية النشر":
                self.start_publishing(chat_id)
            elif text == "العمليات النشطة":
                self.show_active_operations(chat_id)
            elif text == "التحديثات":
                self.show_updates(chat_id)
            elif text == "تهيئة عملية النشر":
                self.show_setup_menu(chat_id)
        
        # معالجة الـ Callback Queries
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            self.handle_callback(call)
    
    def show_main_menu(self, chat_id):
        """عرض القائمة الرئيسية"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton("بدء عملية النشر"))
        keyboard.add(
            KeyboardButton("العمليات النشطة"), 
            KeyboardButton("التحديثات")
        )
        keyboard.add(KeyboardButton("تهيئة عملية النشر"))
        
        self.bot.send_message(
            chat_id,
            "مرحباً! اختر من القائمة:",
            reply_markup=keyboard
        )
    
    def show_admin_menu(self, chat_id):
        """عرض قائمة المدير"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("سحب رقم", callback_data="admin_numbers"))
        keyboard.add(InlineKeyboardButton("إدارة المستخدمين", callback_data="admin_users"))
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        
        self.bot.send_message(
            chat_id,
            "لوحة المدير:",
            reply_markup=keyboard
        )
    
    def show_setup_menu(self, chat_id):
        """عرض قائمة التهيئة"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("تسجيل حساب", callback_data="register_account"))
        keyboard.add(InlineKeyboardButton("المجموعة الهدف", callback_data="target_groups"))
        keyboard.add(InlineKeyboardButton("الفاصل الزمني", callback_data="interval_setup"))
        keyboard.add(InlineKeyboardButton("رسالة النشر", callback_data="message_text"))
        keyboard.add(InlineKeyboardButton("بدء النشر", callback_data="confirm_start"))
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        
        self.bot.send_message(
            chat_id,
            "تهيئة عملية النشر:",
            reply_markup=keyboard
        )
    
    def start_publishing(self, chat_id):
        """بدء عملية النشر"""
        user_settings = self.db.get_user_settings(chat_id)
        user = self.db.get_user(chat_id)
        
        if not user:
            self.bot.send_message(chat_id, "❌ يجب تسجيل حساب أولاً")
            return
        
        if not user_settings:
            self.bot.send_message(chat_id, "❌ يجب تهيئة عملية النشر أولاً")
            return
        
        # التحقق من اكتمال الإعدادات
        if not user_settings[1] or not user_settings[2] or not user_settings[3]:
            self.bot.send_message(chat_id, "❌ يجب إكمال جميع إعدادات النشر أولاً")
            return
        
        # إنشاء عملية جديدة
        groups = json.loads(user_settings[1])
        process_id = self.db.save_process(
            chat_id, groups, user_settings[2], user_settings[3]
        )
        
        # بدء الجدولة
        self.scheduler.start_process(process_id)
        
        self.bot.send_message(
            chat_id, 
            f"✅ بدأت عملية النشر بنجاح!\n"
            f"📊 عدد المجموعات: {len(groups)}\n"
            f"⏰ الفاصل الزمني: {user_settings[3]} دقيقة\n"
            f"🆔 رقم العملية: {process_id}"
        )
    
    def show_active_operations(self, chat_id):
        """عرض العمليات النشطة"""
        processes = self.db.get_user_processes(chat_id)
        
        if not processes:
            self.bot.send_message(chat_id, "❌ لا توجد عمليات نشطة")
            return
        
        keyboard = InlineKeyboardMarkup()
        for process in processes:
            groups_count = len(json.loads(process[2]))
            keyboard.add(InlineKeyboardButton(
                f"العملية {process[0]} - {groups_count} مجموعة - {process[5]}",
                callback_data=f"process_{process[0]}"
            ))
        
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        
        self.bot.send_message(
            chat_id,
            "العمليات النشطة:",
            reply_markup=keyboard
        )
    
    def show_updates(self, chat_id):
        """عرض التحديثات"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            "قناة الاشتراك الإجباري", 
            url=f"https://t.me/{CHANNEL_USERNAME}"
        ))
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        
        self.bot.send_message(
            chat_id,
            "التحديثات والإشتراك الإجباري:",
            reply_markup=keyboard
        )
    
    def handle_callback(self, call):
        """معالجة الـ Callback Queries"""
        chat_id = call.message.chat.id
        data = call.data
        
        try:
            if data == "back_main":
                self.show_main_menu(chat_id)
            elif data == "register_account":
                self.start_auth(chat_id)
            elif data == "target_groups":
                self.show_groups_selection(chat_id)
            elif data == "interval_setup":
                self.show_interval_selection(chat_id)
            elif data == "message_text":
                self.request_message(chat_id)
            elif data == "confirm_start":
                self.confirm_start_publishing(chat_id)
            elif data.startswith("interval_"):
                interval = int(data.split("_")[1])
                self.set_interval(chat_id, interval)
            elif data in ["prev_page", "next_page"]:
                self.handle_groups_pagination(chat_id, data)
            elif data.startswith("toggle_group_"):
                group_id = int(data.split("_")[2])
                self.toggle_group_selection(chat_id, group_id)
            elif data == "set_groups":
                self.save_groups_selection(chat_id)
            elif data == "admin_numbers":
                self.show_user_numbers(chat_id)
            elif data == "admin_users":
                self.show_user_management(chat_id)
            elif data.startswith("process_"):
                process_id = int(data.split("_")[1])
                self.show_process_details(chat_id, process_id)
            elif data.startswith("pause_"):
                process_id = int(data.split("_")[1])
                self.pause_process(chat_id, process_id)
            elif data.startswith("resume_"):
                process_id = int(data.split("_")[1])
                self.resume_process(chat_id, process_id)
            elif data.startswith("delete_"):
                process_id = int(data.split("_")[1])
                self.delete_process(chat_id, process_id)
            elif data.startswith("stats_"):
                process_id = int(data.split("_")[1])
                self.show_process_stats(chat_id, process_id)
                
            self.bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            self.bot.answer_callback_query(call.id, "❌ حدث خطأ")
    
    def start_auth(self, chat_id):
        """بدء عملية المصادقة"""
        self.user_states[chat_id] = {'auth_step': 'phone'}
        self.bot.send_message(
            chat_id,
            "أرسل رقم هاتفك مع رمز الدولة (مثال: +201234567890):",
            reply_markup=ReplyKeyboardRemove()
        )
    
    @self.bot.message_handler(func=lambda message: self.user_states.get(message.chat.id, {}).get('auth_step') == 'phone')
    def handle_phone(self, message):
        """معالجة رقم الهاتف"""
        chat_id = message.chat.id
        phone = message.text
        
        def auth_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                client, phone_code_hash = loop.run_until_complete(
                    self.telethon_manager.authenticate_user(phone)
                )
                
                self.user_states[chat_id] = {
                    'auth_step': 'code',
                    'phone': phone,
                    'phone_code_hash': phone_code_hash,
                    'client': client
                }
                
                self.bot.send_message(chat_id, "أرسل كود التحقق الذي استلمته:")
                
            except Exception as e:
                self.bot.send_message(chat_id, f"❌ خطأ: {str(e)}")
        
        threading.Thread(target=auth_thread).start()
    
    @self.bot.message_handler(func=lambda message: self.user_states.get(message.chat.id, {}).get('auth_step') == 'code')
    def handle_code(self, message):
        """معالجة كود التحقق"""
        chat_id = message.chat.id
        code = message.text
        user_state = self.user_states.get(chat_id, {})
        
        if not all(k in user_state for k in ['phone', 'phone_code_hash', 'client']):
            self.bot.send_message(chat_id, "❌ جلسة المصادقة منتهية، يرجى المحاولة مرة أخرى")
            return
        
        def verify_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                session_string = loop.run_until_complete(
                    self.telethon_manager.verify_code(
                        user_state['client'],
                        user_state['phone'],
                        code,
                        user_state['phone_code_hash']
                    )
                )
                
                # حفظ المستخدم في قاعدة البيانات
                self.db.save_user(chat_id, user_state['phone'], session_string)
                
                # تنظيف حالة المستخدم
                if chat_id in self.user_states:
                    del self.user_states[chat_id]
                
                self.bot.send_message(chat_id, "✅ تم تسجيل الحساب بنجاح!")
                self.show_main_menu(chat_id)
                
            except Exception as e:
                self.bot.send_message(chat_id, f"❌ خطأ في التسجيل: {str(e)}")
        
        threading.Thread(target=verify_thread).start()
    
    def show_groups_selection(self, chat_id):
        """عرض اختيار المجموعات"""
        user = self.db.get_user(chat_id)
        if not user:
            self.bot.send_message(chat_id, "❌ يجب تسجيل حساب أولاً")
            return
        
        def get_groups_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                groups = loop.run_until_complete(
                    self.telethon_manager.get_user_groups(user[2])  # session_string
                )
                
                if not groups:
                    self.bot.send_message(chat_id, "❌ لم يتم العثور على مجموعات أو قنوات")
                    return
                
                # حفظ المجموعات مؤقتاً
                if chat_id not in self.user_states:
                    self.user_states[chat_id] = {}
                
                self.user_states[chat_id]['available_groups'] = groups
                self.user_states[chat_id]['selected_groups'] = []
                self.user_states[chat_id]['groups_page'] = 0
                
                self.display_groups_page(chat_id)
                
            except Exception as e:
                self.bot.send_message(chat_id, f"❌ خطأ في جلب المجموعات: {str(e)}")
        
        threading.Thread(target=get_groups_thread).start()
    
    def display_groups_page(self, chat_id):
        """عرض صفحة المجموعات"""
        user_state = self.user_states.get(chat_id, {})
        groups = user_state.get('available_groups', [])
        selected_groups = user_state.get('selected_groups', [])
        page = user_state.get('groups_page', 0)
        
        items_per_page = 8
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_groups = groups[start_idx:end_idx]
        
        keyboard = InlineKeyboardMarkup()
        for group in page_groups:
            is_selected = group['id'] in selected_groups
            emoji = "✅" if is_selected else "◻️"
            keyboard.add(InlineKeyboardButton(
                f"{emoji} {group['name']}", 
                callback_data=f"toggle_group_{group['id']}"
            ))
        
        # أزرار التنقل
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("السابق", callback_data="prev_page"))
        if end_idx < len(groups):
            nav_buttons.append(InlineKeyboardButton("التالي", callback_data="next_page"))
        
        if nav_buttons:
            keyboard.row(*nav_buttons)
        
        keyboard.add(InlineKeyboardButton("تعيين", callback_data="set_groups"))
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        
        self.bot.send_message(
            chat_id,
            f"اختر المجموعات (الصفحة {page + 1}):",
            reply_markup=keyboard
        )
    
    def toggle_group_selection(self, chat_id, group_id):
        """تبديل اختيار المجموعة"""
        if chat_id not in self.user_states:
            self.user_states[chat_id] = {}
        
        selected_groups = self.user_states[chat_id].get('selected_groups', [])
        
        if group_id in selected_groups:
            selected_groups.remove(group_id)
        else:
            selected_groups.append(group_id)
        
        self.user_states[chat_id]['selected_groups'] = selected_groups
        self.display_groups_page(chat_id)
    
    def handle_groups_pagination(self, chat_id, action):
        """معالجة التنقل بين الصفحات"""
        if chat_id not in self.user_states:
            return
        
        current_page = self.user_states[chat_id].get('groups_page', 0)
        
        if action == "prev_page" and current_page > 0:
            self.user_states[chat_id]['groups_page'] = current_page - 1
        elif action == "next_page":
            self.user_states[chat_id]['groups_page'] = current_page + 1
        
        self.display_groups_page(chat_id)
    
    def save_groups_selection(self, chat_id):
        """حفظ اختيار المجموعات"""
        user_state = self.user_states.get(chat_id, {})
        selected_groups = user_state.get('selected_groups', [])
        
        if not selected_groups:
            self.bot.send_message(chat_id, "❌ لم يتم اختيار أي مجموعات")
            return
        
        self.db.save_user_settings(chat_id, selected_groups=selected_groups)
        self.bot.send_message(chat_id, f"✅ تم تعيين {len(selected_groups)} مجموعة")
    
    def show_interval_selection(self, chat_id):
        """عرض اختيار الفاصل الزمني"""
        keyboard = InlineKeyboardMarkup()
        intervals = [
            ("2 دقائق", 2),
            ("5 دقائق", 5),
            ("10 دقائق", 10),
            ("20 دقيقة", 20),
            ("1 ساعة", 60),
            ("1 يوم", 1440),
            ("2 يوم", 2880)
        ]
        
        for text, minutes in intervals:
            keyboard.add(InlineKeyboardButton(text, callback_data=f"interval_{minutes}"))
        
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        
        self.bot.send_message(
            chat_id,
            "اختر الفاصل الزمني بين الرسائل:",
            reply_markup=keyboard
        )
    
    def set_interval(self, chat_id, interval):
        """تعيين الفاصل الزمني"""
        self.db.save_user_settings(chat_id, interval=interval)
        
        intervals_text = {
            2: "2 دقائق", 5: "5 دقائق", 10: "10 دقائق", 20: "20 دقيقة",
            60: "1 ساعة", 1440: "1 يوم", 2880: "2 يوم"
        }
        
        self.bot.send_message(
            chat_id, 
            f"✅ تم تعيين الفاصل الزمني: {intervals_text[interval]}"
        )
    
    def request_message(self, chat_id):
        """طلب رسالة النشر"""
        self.user_states[chat_id] = {'waiting_for_message': True}
        self.bot.send_message(
            chat_id,
            "أرسل رسالة النشر التي تريد إرسالها:",
            reply_markup=ReplyKeyboardRemove()
        )
    
    @self.bot.message_handler(func=lambda message: self.user_states.get(message.chat.id, {}).get('waiting_for_message'))
    def handle_message_text(self, message):
        """معالجة رسالة النشر"""
        chat_id = message.chat.id
        message_text = message.text
        
        self.db.save_user_settings(chat_id, message_text=message_text)
        
        if chat_id in self.user_states and 'waiting_for_message' in self.user_states[chat_id]:
            del self.user_states[chat_id]['waiting_for_message']
        
        self.bot.send_message(chat_id, "✅ تم حفظ رسالة النشر")
        self.show_main_menu(chat_id)
    
    def confirm_start_publishing(self, chat_id):
        """تأكيد بدء النشر"""
        user_settings = self.db.get_user_settings(chat_id)
        user = self.db.get_user(chat_id)
        
        if not user:
            self.bot.send_message(chat_id, "❌ يجب تسجيل حساب أولاً")
            return
        
        if not user_settings:
            self.bot.send_message(chat_id, "❌ يجب تهيئة عملية النشر أولاً")
            return
        
        required_fields = [user_settings[1], user_settings[2], user_settings[3]]  # groups, message, interval
        if not all(required_fields):
            self.bot.send_message(chat_id, "❌ يجب إكمال جميع إعدادات النشر أولاً")
            return
        
        self.bot.send_message(
            chat_id,
            "✅ تم تهيئة عملية النشر بنجاح! يمكنك الآن البدء بالنشر من القائمة الرئيسية."
        )
    
    def show_process_details(self, chat_id, process_id):
        """عرض تفاصيل العملية"""
        process = self.db.get_process(process_id)
        if not process or process[1] != chat_id:  # user_id
            self.bot.send_message(chat_id, "❌ العملية غير موجودة")
            return
        
        groups = json.loads(process[2])
        stats = self.db.get_process_stats(process_id)
        
        keyboard = InlineKeyboardMarkup()
        if process[5] == 'active':  # status
            keyboard.add(InlineKeyboardButton("إيقاف مؤقت", callback_data=f"pause_{process_id}"))
        else:
            keyboard.add(InlineKeyboardButton("استئناف", callback_data=f"resume_{process_id}"))
        
        keyboard.add(InlineKeyboardButton("حذف العملية", callback_data=f"delete_{process_id}"))
        keyboard.add(InlineKeyboardButton("إحصائيات", callback_data=f"stats_{process_id}"))
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="active_operations"))
        
        message = (
            f"🆔 رقم العملية: {process_id}\n"
            f"📊 عدد المجموعات: {len(groups)}\n"
            f"⏰ الفاصل الزمني: {process[4]} دقيقة\n"
            f"📝 الرسالة: {process[3][:50]}...\n"
            f"📈 الحالة: {process[5]}\n"
            f"🕒 تاريخ البدء: {process[6]}"
        )
        
        self.bot.send_message(chat_id, message, reply_markup=keyboard)
    
    def pause_process(self, chat_id, process_id):
        """إيقاف العملية مؤقتاً"""
        self.scheduler.stop_process(process_id)
        self.db.update_process_status(process_id, 'paused')
        self.bot.send_message(chat_id, "✅ تم إيقاف العملية مؤقتاً")
        self.show_process_details(chat_id, process_id)
    
    def resume_process(self, chat_id, process_id):
        """استئناف العملية"""
        self.scheduler.start_process(process_id)
        self.db.update_process_status(process_id, 'active')
        self.bot.send_message(chat_id, "✅ تم استئناف العملية")
        self.show_process_details(chat_id, process_id)
    
    def delete_process(self, chat_id, process_id):
        """حذف العملية"""
        self.scheduler.stop_process(process_id)
        # Note: في تطبيق حقيقي، قد ترغب في حذف العملية من قاعدة البيانات أيضاً
        self.bot.send_message(chat_id, "✅ تم حذف العملية")
        self.show_active_operations(chat_id)
    
    def show_process_stats(self, chat_id, process_id):
        """عرض إحصائيات العملية"""
        stats = self.db.get_process_stats(process_id)
        if not stats:
            self.bot.send_message(chat_id, "❌ لا توجد إحصائيات لهذه العملية")
            return
        
        total = stats[0] or 0
        successful = stats[1] or 0
        failed = total - successful
        
        message = (
            f"📊 إحصائيات العملية {process_id}:\n"
            f"✅ الرسائل الناجحة: {successful}\n"
            f"❌ الرسائل الفاشلة: {failed}\n"
            f"📈 إجمالي المحاولات: {total}\n"
            f"🎯 نسبة النجاح: {((successful/total)*100 if total > 0 else 0):.1f}%"
        )
        
        self.bot.send_message(chat_id, message)
    
    def show_user_numbers(self, chat_id):
        """عرض أرقام المستخدمين (للمدير)"""
        if chat_id != ADMIN_ID:
            self.bot.send_message(chat_id, "❌ ليس لديك صلاحية الوصول")
            return
        
        users = self.db.get_all_users()
        if not users:
            self.bot.send_message(chat_id, "❌ لا توجد أرقام مسجلة")
            return
        
        message = "أرقام المستخدمين:\n\n"
        for user in users:
            status = "🔴 محظور" if user[3] else "🟢 نشط"
            message += f"📱 {user[1]} - {status} (ID: {user[0]})\n"
        
        self.bot.send_message(chat_id, message)
    
    def show_user_management(self, chat_id):
        """إدارة المستخدمين (للمدير)"""
        if chat_id != ADMIN_ID:
            self.bot.send_message(chat_id, "❌ ليس لديك صلاحية الوصول")
            return
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("حظر شخص", callback_data="ban_user"))
        keyboard.add(InlineKeyboardButton("إيقاف حظر شخص", callback_data="unban_user"))
        keyboard.add(InlineKeyboardButton("رجوع", callback_data="back_main"))
        
        self.bot.send_message(chat_id, "إدارة المستخدمين:", reply_markup=keyboard)
    
    def run(self):
        """تشغيل البوت"""
        logger.info("Bot is running...")
        try:
            self.bot.infinity_polling()
        except Exception as e:
            logger.error(f"Bot error: {e}")
            # إعادة التشغيل التلقائي في حالة الخطأ
            time.sleep(5)
            self.run()

# ============================
# التشغيل الرئيسي
# ============================

if __name__ == "__main__":
    # التأكد من وجود ملفات التخزين
    if not os.path.exists("auto_poster.db"):
        print("سيتم إنشاء قاعدة البيانات لأول مرة...")
    
    # تشغيل البوت
    bot = TelegramAutoPosterBot()
    bot.run()
