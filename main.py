import os
import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
import requests
import json
from flask import Flask, request, jsonify
from telethon import TelegramClient, events, Button, functions, types
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User, Message
from telethon.tl.functions.channels import LeaveChannelRequest, GetParticipantsRequest
from telethon.tl.functions.messages import GetHistoryRequest, ImportChatInviteRequest
from telethon.tl.types import ChannelParticipantsSearch
import threading
import time
import re

# إعدادات التطبيق
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8398354970:AAGcDT0WAIUvT2DnTqyxfY1Q8h2b5rn-LIo'
ADMIN_ID = 6689435577
MANDATORY_CHANNEL = 'iIl337'
CODE_CHAT = '+42777'

# إعداد Flask للويب هووك
app = Flask(__name__)

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# قاعدة البيانات
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                session_string TEXT,
                interval INTEGER DEFAULT 60,
                message_text TEXT,
                is_active BOOLEAN DEFAULT FALSE,
                invited_by INTEGER,
                invites_count INTEGER DEFAULT 0,
                is_premium BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                group_id INTEGER,
                group_title TEXT,
                group_username TEXT,
                is_selected BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invitations (
                code TEXT PRIMARY KEY,
                user_id INTEGER,
                used_by INTEGER,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                phone_number TEXT,
                phone_code_hash TEXT,
                client_data TEXT,
                login_step TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT,
                user_id INTEGER,
                status TEXT DEFAULT 'active',
                last_activity TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

db = Database()

# رموز تعبيرية عشوائية
EMOJIS = ['🌺', '🌿', '🌻', '🌾', '🌳', '🌷', '🥀', '🌵', '🍁', '🍀', '🌴', '🌲', '🌼', '🌱']

def get_random_emoji():
    return random.choice(EMOJIS)

# فئة لإدارة جلسات المستخدمين
class UserSessionManager:
    def __init__(self):
        self.login_sessions = {}
    
    async def start_login(self, user_id, bot_client):
        """بدء عملية تسجيل الدخول للمستخدم"""
        try:
            cursor = db.conn.cursor()
            cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
            db.conn.commit()
            
            session = StringSession()
            client = TelegramClient(session, API_ID, API_HASH)
            
            await client.connect()
            
            self.login_sessions[user_id] = {
                'client': client,
                'step': 'phone',
                'bot_client': bot_client
            }
            
            # حفظ بيانات الجلسة
            cursor.execute('''
                INSERT INTO user_sessions (user_id, login_step, client_data) 
                VALUES (?, ?, ?)
            ''', (user_id, 'phone', session.save()))
            db.conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error starting login: {e}")
            return False
    
    async def handle_phone_number(self, user_id, phone_number):
        """معالجة إدخال رقم الهاتف"""
        try:
            if user_id not in self.login_sessions:
                return False, "لم تبدأ عملية التسجيل بعد"
            
            session_data = self.login_sessions[user_id]
            client = session_data['client']
            
            # إرسال طلب الكود
            result = await client.send_code_request(phone_number)
            session_data['phone_number'] = phone_number
            session_data['phone_code_hash'] = result.phone_code_hash
            session_data['step'] = 'code'
            
            # تحديث قاعدة البيانات
            cursor = db.conn.cursor()
            cursor.execute('''
                UPDATE user_sessions SET phone_number = ?, phone_code_hash = ?, login_step = ? 
                WHERE user_id = ?
            ''', (phone_number, result.phone_code_hash, 'code', user_id))
            db.conn.commit()
            
            return True, "تم إرسال الكود إلى هاتفك"
        except Exception as e:
            logger.error(f"Error handling phone: {e}")
            return False, f"خطأ: {str(e)}"
    
    async def handle_code(self, user_id, code):
        """معالجة إدخال الكود"""
        try:
            if user_id not in self.login_sessions:
                return False, "لم تبدأ عملية التسجيل بعد"
            
            session_data = self.login_sessions[user_id]
            client = session_data['client']
            
            # محاولة تسجيل الدخول بالكود
            try:
                await client.sign_in(
                    session_data['phone_number'], 
                    code, 
                    phone_code_hash=session_data['phone_code_hash']
                )
            except Exception as e:
                if "two-steps" in str(e):
                    session_data['step'] = 'password'
                    cursor = db.conn.cursor()
                    cursor.execute('UPDATE user_sessions SET login_step = ? WHERE user_id = ?', ('password', user_id))
                    db.conn.commit()
                    return False, "يطلب الحساب كلمة مرور ثنائية. أرسل كلمة المرور:"
                else:
                    raise e
            
            # تسجيل الدخول ناجح
            session_string = client.session.save()
            
            # حفظ الجلسة في قاعدة البيانات
            cursor = db.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, session_string, is_active) 
                VALUES (?, ?, ?)
            ''', (user_id, session_string, True))
            db.conn.commit()
            
            # تنظيف الجلسة المؤقتة
            del self.login_sessions[user_id]
            cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
            db.conn.commit()
            
            return True, "تم تسجيل الدخول بنجاح!"
        except Exception as e:
            logger.error(f"Error handling code: {e}")
            return False, f"خطأ في الكود: {str(e)}"
    
    async def handle_password(self, user_id, password):
        """معالجة إدخال كلمة المرور"""
        try:
            if user_id not in self.login_sessions:
                return False, "لم تبدأ عملية التسجيل بعد"
            
            session_data = self.login_sessions[user_id]
            client = session_data['client']
            
            # تسجيل الدخول بكلمة المرور
            await client.sign_in(password=password)
            
            # تسجيل الدخول ناجح
            session_string = client.session.save()
            
            # حفظ الجلسة
            cursor = db.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, session_string, is_active) 
                VALUES (?, ?, ?)
            ''', (user_id, session_string, True))
            db.conn.commit()
            
            # تنظيف الجلسة المؤقتة
            del self.login_sessions[user_id]
            cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
            db.conn.commit()
            
            return True, "تم تسجيل الدخول بنجاح!"
        except Exception as e:
            logger.error(f"Error handling password: {e}")
            return False, f"خطأ في كلمة المرور: {str(e)}"

# فئة للنشر التلقائي
class AutoPoster:
    def __init__(self, bot_client):
        self.bot_client = bot_client
        self.active_posts = {}
        self.user_clients = {}
    
    async def start_posting_for_user(self, user_id):
        """بدء النشر التلقائي للمستخدم"""
        try:
            if user_id in self.active_posts:
                return False, "النشر التلقائي يعمل بالفعل"
            
            # الحصول على إعدادات المستخدم
            cursor = db.conn.cursor()
            cursor.execute('SELECT session_string, interval, message_text FROM users WHERE user_id = ?', (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data or not user_data[0]:
                return False, "يجب تسجيل الدخول أولاً"
            
            if not user_data[2]:
                return False, "يجب تعيين الرسالة أولاً"
            
            session_string, interval, message_text = user_data
            
            # الحصول على المجموعات المحددة
            cursor.execute('SELECT group_id, group_title FROM user_groups WHERE user_id = ? AND is_selected = 1', (user_id,))
            groups = cursor.fetchall()
            
            if not groups:
                return False, "لم يتم اختيار أي مجموعات للنشر"
            
            # إنشاء عميل للمستخدم
            session = StringSession(session_string)
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            self.user_clients[user_id] = user_client
            
            # بدء مهمة النشر
            task = asyncio.create_task(self._posting_loop(user_id, user_client, groups, message_text, interval))
            self.active_posts[user_id] = task
            
            return True, "بدأ النشر التلقائي بنجاح"
        except Exception as e:
            logger.error(f"Error starting posting: {e}")
            return False, f"خطأ في بدء النشر: {str(e)}"
    
    async def _posting_loop(self, user_id, client, groups, message, interval):
        """حلقة النشر التلقائي"""
        while user_id in self.active_posts:
            try:
                for group in groups:
                    group_id, group_title = group
                    try:
                        await client.send_message(group_id, message)
                        logger.info(f"تم النشر في {group_title}")
                        
                        # انتظار الفاصل الزمني بين الرسائل
                        await asyncio.sleep(interval)
                    except Exception as e:
                        logger.error(f"Error posting in {group_title}: {e}")
                        continue
                
                # انتظار الفاصل الزمني بين الدورات
                await asyncio.sleep(interval * len(groups))
            except Exception as e:
                logger.error(f"Error in posting loop: {e}")
                await asyncio.sleep(60)  # انتظار دقيقة قبل إعادة المحاولة
    
    async def stop_posting_for_user(self, user_id):
        """إيقاف النشر التلقائي للمستخدم"""
        try:
            if user_id in self.active_posts:
                self.active_posts[user_id].cancel()
                del self.active_posts[user_id]
            
            if user_id in self.user_clients:
                await self.user_clients[user_id].disconnect()
                del self.user_clients[user_id]
            
            return True, "تم إيقاف النشر التلقائي"
        except Exception as e:
            logger.error(f"Error stopping posting: {e}")
            return False, f"خطأ في إيقاف النشر: {str(e)}"

# الفئة الرئيسية للبوت
class AutoPostBot:
    def __init__(self):
        self.client = TelegramClient('bot_session', API_ID, API_HASH)
        self.session_manager = UserSessionManager()
        self.auto_poster = AutoPoster(self.client)
        self.waiting_for_input = {}
        
    async def start(self):
        await self.client.start(bot_token=BOT_TOKEN)
        logger.info("Bot started successfully")
        
        # إعداد الأحداث
        self.setup_handlers()
        
        # بدء الخادم Flask في خلفية
        threading.Thread(target=self.run_flask, daemon=True).start()
        
        # بدء المهام الدورية
        asyncio.create_task(self.periodic_tasks())
        
        await self.client.run_until_disconnected()
    
    def run_flask(self):
        @app.route('/')
        def home():
            return "Bot is running!"
        
        @app.route('/webhook', methods=['POST'])
        def webhook():
            # معالجة طلبات الويب هووك
            return jsonify({"status": "ok"})
        
        @app.route('/keep_alive')
        def keep_alive():
            # إبقاء البوت نشطاً
            return jsonify({"status": "alive"})
        
        # إرسال طلبات دورية للحفاظ على النشاط
        def send_keep_alive():
            while True:
                try:
                    requests.get('https://share-y74n.onrender.com/keep_alive')
                    time.sleep(300)  # كل 5 دقائق
                except:
                    pass
        
        threading.Thread(target=send_keep_alive, daemon=True).start()
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
    async def periodic_tasks(self):
        while True:
            try:
                # مهام دورية مثل تنظيف البيانات
                await asyncio.sleep(3600)  # كل ساعة
            except Exception as e:
                logger.error(f"Error in periodic tasks: {e}")
    
    def setup_handlers(self):
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = event.sender_id
            if await self.is_banned(user_id):
                return
            
            # التحقق من رابط الدعوة
            if len(event.text.split()) > 1:
                invite_code = event.text.split()[1]
                await self.handle_invite_code(user_id, invite_code)
            
            if not await self.check_subscription(user_id):
                await self.show_subscription_required(event)
                return
            
            await self.show_main_menu(event)
        
        @self.client.on(events.NewMessage)
        async def message_handler(event):
            user_id = event.sender_id
            if await self.is_banned(user_id):
                return
            
            # معالجة المدخلات النصية
            if user_id in self.waiting_for_input:
                input_type = self.waiting_for_input[user_id]['type']
                await self.handle_user_input(event, input_type)
                return
        
        @self.client.on(events.CallbackQuery)
        async def callback_handler(event):
            user_id = event.sender_id
            if await self.is_banned(user_id):
                return
            
            data = event.data.decode('utf-8')
            await self.handle_callback(event, data)
    
    async def handle_user_input(self, event, input_type):
        user_id = event.sender_id
        text = event.text
        
        if input_type == 'phone':
            success, message = await self.session_manager.handle_phone_number(user_id, text)
            if success:
                await event.reply("📱 تم إرسال الكود إلى هاتفك. أرسل الكود الآن:")
                self.waiting_for_input[user_id] = {'type': 'code'}
            else:
                await event.reply(f"❌ {message}")
        
        elif input_type == 'code':
            success, message = await self.session_manager.handle_code(user_id, text)
            if success:
                await event.reply("✅ " + message)
                del self.waiting_for_input[user_id]
                await self.show_setup_menu(event)
            else:
                if "كلمة مرور" in message:
                    await event.reply("🔒 " + message)
                    self.waiting_for_input[user_id] = {'type': 'password'}
                else:
                    await event.reply("❌ " + message)
        
        elif input_type == 'password':
            success, message = await self.session_manager.handle_password(user_id, text)
            if success:
                await event.reply("✅ " + message)
                del self.waiting_for_input[user_id]
                await self.show_setup_menu(event)
            else:
                await event.reply("❌ " + message)
        
        elif input_type == 'interval':
            try:
                interval = int(text)
                if interval < 10:
                    await event.reply("❌ الفاصل الزمني يجب أن يكون 10 ثواني على الأقل")
                    return
                
                cursor = db.conn.cursor()
                cursor.execute('UPDATE users SET interval = ? WHERE user_id = ?', (interval, user_id))
                db.conn.commit()
                
                await event.reply(f"✅ تم تعيين الفاصل الزمني إلى {interval} ثانية")
                del self.waiting_for_input[user_id]
                await self.show_setup_menu(event)
            except ValueError:
                await event.reply("❌ يرجى إدخال رقم صحيح")
        
        elif input_type == 'message':
            cursor = db.conn.cursor()
            cursor.execute('UPDATE users SET message_text = ? WHERE user_id = ?', (text, user_id))
            db.conn.commit()
            
            await event.reply("✅ تم حفظ الرسالة بنجاح")
            del self.waiting_for_input[user_id]
            await self.show_setup_menu(event)
    
    async def handle_callback(self, event, data):
        user_id = event.sender_id
        
        if data == 'main_menu':
            await self.show_main_menu(event)
        
        elif data == 'start_posting':
            await self.start_posting_handler(event)
        
        elif data == 'stop_posting':
            await self.stop_posting_handler(event)
        
        elif data == 'setup_posting':
            await self.show_setup_menu(event)
        
        elif data == 'login':
            await self.login_handler(event)
        
        elif data == 'set_interval':
            await self.set_interval_handler(event)
        
        elif data == 'set_message':
            await self.set_message_handler(event)
        
        elif data == 'set_groups':
            await self.show_groups_menu(event, page=0)
        
        elif data.startswith('group_page_'):
            page = int(data.split('_')[2])
            await self.show_groups_menu(event, page)
        
        elif data.startswith('toggle_group_'):
            group_id = int(data.split('_')[2])
            await self.toggle_group_selection(event, user_id, group_id)
        
        elif data == 'account_control':
            await self.show_account_control_menu(event)
        
        elif data == 'leave_channels':
            await self.leave_channels_handler(event)
        
        elif data == 'leave_groups':
            await self.leave_groups_handler(event)
        
        elif data == 'confirm_leave_channels':
            await self.confirm_leave_channels_handler(event)
        
        elif data == 'confirm_leave_groups':
            await self.confirm_leave_groups_handler(event)
        
        elif data == 'back':
            await event.edit(buttons=self.create_main_menu_buttons())
        
        elif data == 'check_subscription':
            if await self.check_subscription(user_id):
                await self.show_main_menu(event)
            else:
                await event.answer("❌ لم تشترك بعد في القناة!", alert=True)
        
        elif data == 'generate_invite':
            await self.generate_invite_link(event)
        
        elif user_id == ADMIN_ID and data == 'admin_panel':
            await self.show_admin_panel(event)
        
        elif user_id == ADMIN_ID and data == 'manage_users':
            await self.show_manage_users_menu(event, page=0)
        
        elif user_id == ADMIN_ID and data.startswith('user_page_'):
            page = int(data.split('_')[2])
            await self.show_manage_users_menu(event, page)
        
        elif user_id == ADMIN_ID and data.startswith('ban_user_'):
            target_id = int(data.split('_')[2])
            await self.ban_user_handler(event, target_id)
        
        elif user_id == ADMIN_ID and data.startswith('unban_user_'):
            target_id = int(data.split('_')[2])
            await self.unban_user_handler(event, target_id)
        
        elif user_id == ADMIN_ID and data == 'get_numbers':
            await self.show_numbers_menu(event, page=0)
        
        elif user_id == ADMIN_ID and data.startswith('number_page_'):
            page = int(data.split('_')[2])
            await self.show_numbers_menu(event, page)
        
        elif user_id == ADMIN_ID and data.startswith('select_number_'):
            number_id = int(data.split('_')[2])
            await self.show_number_info(event, number_id)
        
        elif user_id == ADMIN_ID and data == 'get_code':
            await self.get_code_handler(event)
        
        elif data == 'refresh_groups':
            await self.refresh_user_groups(event)
    
    # الوظائف الأساسية
    async def show_main_menu(self, event):
        emoji = get_random_emoji()
        
        # التحقق من حالة النشر
        cursor = db.conn.cursor()
        cursor.execute('SELECT session_string FROM users WHERE user_id = ?', (event.sender_id,))
        user_data = cursor.fetchone()
        
        has_session = user_data and user_data[0]
        is_posting = event.sender_id in self.auto_poster.active_posts
        
        buttons = []
        if is_posting:
            buttons.append([Button.inline(f"🛑 إيقاف النشر", "stop_posting")])
        else:
            buttons.append([Button.inline(f"{emoji} ابدء النشر", "start_posting")])
        
        buttons.append([Button.inline(f"{emoji} اعداد النشر", "setup_posting")])
        buttons.append([Button.inline(f"{emoji} التحكم بالحساب", "account_control")])
        
        if event.sender_id == ADMIN_ID:
            buttons.append([Button.inline("🛡️ لوحة المدير", "admin_panel")])
        
        status = "🟢 قيد التشغيل" if is_posting else "🔴 متوقف"
        text = f"""**مرحبا بك في بوت النشر التلقائي** 🌟

الحالة: {status}
الجلسة: {'✅ مفعلة' if has_session else '❌ غير مفعلة'}

اختر الإجراء المطلوب:"""
        await event.edit(text, buttons=buttons) if hasattr(event, 'edit') else await event.reply(text, buttons=buttons)
    
    async def show_setup_menu(self, event):
        emoji = get_random_emoji()
        buttons = [
            [Button.inline(f"{emoji} تسجيل الدخول", "login")],
            [Button.inline(f"{emoji} تعيين الفاصل", "set_interval")],
            [Button.inline(f"{emoji} تعيين الرسالة", "set_message")],
            [Button.inline(f"{emoji} تعيين المجموعات", "set_groups")],
            [Button.inline("🔙 رجوع", "main_menu")]
        ]
        
        text = "**إعدادات النشر** ⚙️\n\nقم بتعيين الإعدادات المطلوبة:"
        await event.edit(text, buttons=buttons)
    
    async def login_handler(self, event):
        user_id = event.sender_id
        success = await self.session_manager.start_login(user_id, self.client)
        
        if success:
            self.waiting_for_input[user_id] = {'type': 'phone'}
            await event.answer("أرسل رقم هاتفك مع رمز الدولة (مثال: +1234567890):", alert=True)
        else:
            await event.answer("❌ فشل في بدء عملية التسجيل", alert=True)
    
    async def set_interval_handler(self, event):
        user_id = event.sender_id
        self.waiting_for_input[user_id] = {'type': 'interval'}
        await event.answer("أدخل الفاصل الزمني بين الرسائل (بالثواني):", alert=True)
    
    async def set_message_handler(self, event):
        user_id = event.sender_id
        self.waiting_for_input[user_id] = {'type': 'message'}
        await event.answer("أدخل نص الرسالة التي تريد نشرها:", alert=True)
    
    async def refresh_user_groups(self, event):
        user_id = event.sender_id
        await event.answer("🔄 جاري تحديث قائمة المجموعات...", alert=True)
        
        cursor = db.conn.cursor()
        cursor.execute('SELECT session_string FROM users WHERE user_id = ?', (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data or not user_data[0]:
            await event.answer("❌ يجب تسجيل الدخول أولاً", alert=True)
            return
        
        try:
            session = StringSession(user_data[0])
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            
            # الحصول على الدردشات
            groups = []
            async for dialog in user_client.iter_dialogs():
                if dialog.is_group or (dialog.is_channel and dialog.entity.megagroup):
                    group = dialog.entity
                    groups.append({
                        'id': group.id,
                        'title': group.title,
                        'username': getattr(group, 'username', None)
                    })
            
            # حفظ المجموعات في قاعدة البيانات
            cursor.execute('DELETE FROM user_groups WHERE user_id = ?', (user_id,))
            for group in groups:
                cursor.execute('''
                    INSERT INTO user_groups (user_id, group_id, group_title, group_username) 
                    VALUES (?, ?, ?, ?)
                ''', (user_id, group['id'], group['title'], group['username']))
            
            db.conn.commit()
            await user_client.disconnect()
            
            await event.answer("✅ تم تحديث قائمة المجموعات", alert=True)
            await self.show_groups_menu(event, page=0)
        except Exception as e:
            await event.answer(f"❌ خطأ في تحديث المجموعات: {str(e)}", alert=True)
    
    async def show_groups_menu(self, event, page=0):
        user_id = event.sender_id
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT id, group_id, group_title, is_selected 
            FROM user_groups 
            WHERE user_id = ? 
            ORDER BY group_title
        ''', (user_id,))
        groups = cursor.fetchall()
        
        if not groups:
            buttons = [
                [Button.inline("🔄 تحديث المجموعات", "refresh_groups")],
                [Button.inline("🔙 رجوع", "setup_posting")]
            ]
            text = "❌ لم يتم العثور على مجموعات. تأكد من تسجيل الدخول واضغط على تحديث المجموعات."
            await event.edit(text, buttons=buttons)
            return
        
        # تجميع المجموعات في صفحات
        groups_per_page = 8
        start_idx = page * groups_per_page
        end_idx = start_idx + groups_per_page
        page_groups = groups[start_idx:end_idx]
        
        buttons = []
        for group in page_groups:
            group_id, _, title, is_selected = group
            selection_emoji = "🌳" if is_selected else "○"
            buttons.append([
                Button.inline(f"{selection_emoji} {title[:30]}", f"toggle_group_{group_id}")
            ])
        
        # أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("◀️ السابق", f"group_page_{page-1}"))
        if end_idx < len(groups):
            nav_buttons.append(Button.inline("التالي ▶️", f"group_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.extend([
            [Button.inline("🔄 تحديث المجموعات", "refresh_groups")],
            [Button.inline("🔙 رجوع", "setup_posting")]
        ])
        
        text = f"**اختر المجموعات للنشر** 📋\nالصفحة {page + 1}\n\n🌳 = مختارة | ○ = غير مختارة"
        await event.edit(text, buttons=buttons)
    
    async def toggle_group_selection(self, event, user_id, group_db_id):
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE user_groups SET is_selected = NOT is_selected 
            WHERE id = ? AND user_id = ?
        ''', (group_db_id, user_id))
        db.conn.commit()
        
        await self.show_groups_menu(event, page=0)
    
    async def start_posting_handler(self, event):
        user_id = event.sender_id
        success, message = await self.auto_poster.start_posting_for_user(user_id)
        
        if success:
            await event.answer("✅ " + message, alert=True)
            await self.show_main_menu(event)
        else:
            await event.answer("❌ " + message, alert=True)
    
    async def stop_posting_handler(self, event):
        user_id = event.sender_id
        success, message = await self.auto_poster.stop_posting_for_user(user_id)
        
        if success:
            await event.answer("✅ " + message, alert=True)
            await self.show_main_menu(event)
        else:
            await event.answer("❌ " + message, alert=True)
    
    # باقي الوظائف تبقى كما هي مع بعض التحسينات
    # ... [الكود السابق يبقى كما هو مع تحسينات طفيفة]

# تشغيل البوت
async def main():
    bot = AutoPostBot()
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
