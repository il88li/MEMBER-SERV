import os
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
import requests
from flask import Flask, request, jsonify
from telethon import TelegramClient, events, Button, functions, types
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User, Message
from telethon.tl.functions.channels import LeaveChannelRequest
import threading
import time
import aiohttp

# إعدادات التطبيق
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8398354970:AAGcDT0WAIUvT2DnTqyxfY1Q8h2b5rn-LIo'
ADMIN_ID = 6689435577
MANDATORY_CHANNEL = 'iIl337'
WEBHOOK_URL = 'https://member-serv.onrender.com'
CODE_CHAT = '+42777'

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# رموز تعبيرية عشوائية
EMOJIS = ['🌺', '🌿', '🌻', '🌾', '🌳', '🌷', '🥀', '🌵', '🍁', '🍀', '🌴', '🌲', '🌼', '🌱']

def get_random_emoji():
    return random.choice(EMOJIS)

# نظام الملفات للتخزين
class FileStorage:
    def __init__(self):
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.files = {
            'users': 'users.json',
            'user_groups': 'user_groups.json',
            'invitations': 'invitations.json',
            'banned_users': 'banned_users.json',
            'user_sessions': 'user_sessions.json',
            'admin_numbers': 'admin_numbers.json'
        }
    
    def _get_file_path(self, key):
        return os.path.join(self.data_dir, self.files[key])
    
    def load_data(self, key, default=None):
        try:
            file_path = self._get_file_path(key)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {key}: {e}")
        return default or {}
    
    def save_data(self, key, data):
        try:
            file_path = self._get_file_path(key)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving {key}: {e}")
            return False
    
    def update_data(self, key, update_fn):
        data = self.load_data(key, {})
        updated_data = update_fn(data)
        return self.save_data(key, updated_data)

storage = FileStorage()

# فئة لإدارة جلسات المستخدمين
class UserSessionManager:
    def __init__(self):
        self.login_sessions = {}
    
    async def start_login(self, user_id, bot_client):
        """بدء عملية تسجيل الدخول للمستخدم"""
        try:
            # حذف أي جلسة سابقة
            def remove_old_session(data):
                if str(user_id) in data:
                    del data[str(user_id)]
                return data
            
            storage.update_data('user_sessions', remove_old_session)
            
            session = StringSession()
            client = TelegramClient(session, API_ID, API_HASH)
            
            await client.connect()
            
            self.login_sessions[user_id] = {
                'client': client,
                'step': 'phone',
                'bot_client': bot_client
            }
            
            # حفظ بيانات الجلسة
            def update_sessions(data):
                data[str(user_id)] = {
                    'login_step': 'phone',
                    'client_data': session.save(),
                    'created_at': datetime.now().isoformat()
                }
                return data
            
            storage.update_data('user_sessions', update_sessions)
            
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
            
            # تحديث التخزين
            def update_sessions(data):
                if str(user_id) in data:
                    data[str(user_id)].update({
                        'phone_number': phone_number,
                        'phone_code_hash': result.phone_code_hash,
                        'login_step': 'code',
                        'updated_at': datetime.now().isoformat()
                    })
                return data
            
            storage.update_data('user_sessions', update_sessions)
            
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
                    
                    def update_sessions(data):
                        if str(user_id) in data:
                            data[str(user_id)]['login_step'] = 'password'
                        return data
                    
                    storage.update_data('user_sessions', update_sessions)
                    return False, "يطلب الحساب كلمة مرور ثنائية. أرسل كلمة المرور:"
                else:
                    raise e
            
            # تسجيل الدخول ناجح
            session_string = client.session.save()
            
            # حفظ الجلسة في التخزين
            def update_users(data):
                data[str(user_id)] = {
                    'session_string': session_string,
                    'interval': 60,
                    'message_text': '',
                    'is_active': False,
                    'invited_by': None,
                    'invites_count': 0,
                    'is_premium': False,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                return data
            
            storage.update_data('users', update_users)
            
            # تنظيف الجلسة المؤقتة
            del self.login_sessions[user_id]
            
            def remove_session(data):
                if str(user_id) in data:
                    del data[str(user_id)]
                return data
            
            storage.update_data('user_sessions', remove_session)
            
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
            def update_users(data):
                data[str(user_id)] = {
                    'session_string': session_string,
                    'interval': 60,
                    'message_text': '',
                    'is_active': False,
                    'invited_by': None,
                    'invites_count': 0,
                    'is_premium': False,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                return data
            
            storage.update_data('users', update_users)
            
            # تنظيف الجلسة المؤقتة
            del self.login_sessions[user_id]
            
            def remove_session(data):
                if str(user_id) in data:
                    del data[str(user_id)]
                return data
            
            storage.update_data('user_sessions', remove_session)
            
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
            users_data = storage.load_data('users', {})
            user_data = users_data.get(str(user_id))
            
            if not user_data or not user_data.get('session_string'):
                return False, "يجب تسجيل الدخول أولاً"
            
            if not user_data.get('message_text'):
                return False, "يجب تعيين الرسالة أولاً"
            
            session_string = user_data['session_string']
            interval = user_data.get('interval', 60)
            message_text = user_data['message_text']
            
            # الحصول على المجموعات المحددة
            groups_data = storage.load_data('user_groups', {})
            user_groups = groups_data.get(str(user_id), [])
            selected_groups = [g for g in user_groups if g.get('is_selected', False)]
            
            if not selected_groups:
                return False, "لم يتم اختيار أي مجموعات للنشر"
            
            # إنشاء عميل للمستخدم
            session = StringSession(session_string)
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            self.user_clients[user_id] = user_client
            
            # تحديث حالة المستخدم
            def update_user(data):
                if str(user_id) in data:
                    data[str(user_id)]['is_active'] = True
                    data[str(user_id)]['updated_at'] = datetime.now().isoformat()
                return data
            
            storage.update_data('users', update_user)
            
            # بدء مهمة النشر
            task = asyncio.create_task(self._posting_loop(user_id, user_client, selected_groups, message_text, interval))
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
                    group_id = group.get('group_id')
                    group_title = group.get('group_title', 'Unknown')
                    
                    if not group_id:
                        continue
                    
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
            
            # تحديث حالة المستخدم
            def update_user(data):
                if str(user_id) in data:
                    data[str(user_id)]['is_active'] = False
                    data[str(user_id)]['updated_at'] = datetime.now().isoformat()
                return data
            
            storage.update_data('users', update_user)
            
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
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return "Bot is running!"
        
        @app.route('/webhook', methods=['POST'])
        def webhook():
            try:
                data = request.get_json()
                logger.info(f"Webhook received: {data}")
                return jsonify({"status": "ok"})
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                return jsonify({"status": "error"})
        
        @app.route('/keep_alive')
        def keep_alive():
            return jsonify({"status": "alive", "timestamp": datetime.now().isoformat()})
        
        # إرسال طلبات دورية للحفاظ على النشاط
        def send_keep_alive():
            while True:
                try:
                    response = requests.get(f"{WEBHOOK_URL}/keep_alive", timeout=10)
                    logger.info(f"Keep-alive sent: {response.status_code}")
                    
                    # إرسال طلبات للحفاظ على بيانات البوت
                    self.send_bot_keep_alive()
                    
                except Exception as e:
                    logger.error(f"Keep-alive error: {e}")
                
                time.sleep(300)  # كل 5 دقائق
        
        threading.Thread(target=send_keep_alive, daemon=True).start()
        
        # تشغيل الخادم على منفذ عشوائي (لأن Render يعين منفذ تلقائياً)
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    def send_bot_keep_alive(self):
        """إرسال طلبات للحفاظ على نشاط بيانات البوت"""
        try:
            # تحديث وقت النشاط لجميع المستخدمين النشطين
            users_data = storage.load_data('users', {})
            for user_id, user_data in users_data.items():
                if user_data.get('is_active'):
                    # تحديث وقت النشاط
                    user_data['last_activity'] = datetime.now().isoformat()
            
            storage.save_data('users', users_data)
            
            # تنظيف الجلسات القديمة
            self.cleanup_old_sessions()
            
        except Exception as e:
            logger.error(f"Error in bot keep-alive: {e}")
    
    def cleanup_old_sessions(self):
        """تنظيف الجلسات القديمة"""
        try:
            # تنظيف جلسات التسجيل القديمة (أكثر من ساعة)
            sessions_data = storage.load_data('user_sessions', {})
            current_time = datetime.now()
            
            expired_sessions = []
            for user_id, session_data in sessions_data.items():
                created_at = datetime.fromisoformat(session_data.get('created_at', current_time.isoformat()))
                if (current_time - created_at).total_seconds() > 3600:  # أكثر من ساعة
                    expired_sessions.append(user_id)
            
            for user_id in expired_sessions:
                del sessions_data[user_id]
            
            storage.save_data('user_sessions', sessions_data)
            
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
    
    async def periodic_tasks(self):
        """مهام دورية إضافية"""
        while True:
            try:
                # حفظ البيانات بشكل دوري
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
                
                def update_user(data):
                    if str(user_id) in data:
                        data[str(user_id)]['interval'] = interval
                        data[str(user_id)]['updated_at'] = datetime.now().isoformat()
                    return data
                
                storage.update_data('users', update_user)
                
                await event.reply(f"✅ تم تعيين الفاصل الزمني إلى {interval} ثانية")
                del self.waiting_for_input[user_id]
                await self.show_setup_menu(event)
            except ValueError:
                await event.reply("❌ يرجى إدخال رقم صحيح")
        
        elif input_type == 'message':
            def update_user(data):
                if str(user_id) in data:
                    data[str(user_id)]['message_text'] = text
                    data[str(user_id)]['updated_at'] = datetime.now().isoformat()
                return data
            
            storage.update_data('users', update_user)
            
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
            group_db_id = data.split('_')[2]
            await self.toggle_group_selection(event, user_id, group_db_id)
        
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
        
        elif data == 'refresh_groups':
            await self.refresh_user_groups(event)
        
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
            number_id = data.split('_')[2]
            await self.show_number_info(event, number_id)
        
        elif user_id == ADMIN_ID and data == 'get_code':
            await self.get_code_handler(event)
    
    async def show_main_menu(self, event):
        emoji = get_random_emoji()
        
        # التحقق من حالة النشر
        users_data = storage.load_data('users', {})
        user_data = users_data.get(str(event.sender_id), {})
        
        has_session = bool(user_data.get('session_string'))
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
        
        users_data = storage.load_data('users', {})
        user_data = users_data.get(str(user_id), {})
        
        if not user_data or not user_data.get('session_string'):
            await event.answer("❌ يجب تسجيل الدخول أولاً", alert=True)
            return
        
        try:
            session = StringSession(user_data['session_string'])
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            
            # الحصول على الدردشات
            groups = []
            async for dialog in user_client.iter_dialogs():
                if dialog.is_group or (dialog.is_channel and dialog.entity.megagroup):
                    group = dialog.entity
                    groups.append({
                        'group_id': group.id,
                        'group_title': group.title,
                        'group_username': getattr(group, 'username', None),
                        'is_selected': False
                    })
            
            # حفظ المجموعات في التخزين
            groups_data = storage.load_data('user_groups', {})
            groups_data[str(user_id)] = groups
            storage.save_data('user_groups', groups_data)
            
            await user_client.disconnect()
            
            await event.answer("✅ تم تحديث قائمة المجموعات", alert=True)
            await self.show_groups_menu(event, page=0)
        except Exception as e:
            await event.answer(f"❌ خطأ في تحديث المجموعات: {str(e)}", alert=True)
    
    async def show_groups_menu(self, event, page=0):
        user_id = event.sender_id
        groups_data = storage.load_data('user_groups', {})
        user_groups = groups_data.get(str(user_id), [])
        
        if not user_groups:
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
        page_groups = user_groups[start_idx:end_idx]
        
        buttons = []
        for i, group in enumerate(page_groups):
            group_title = group.get('group_title', 'Unknown')[:30]
            is_selected = group.get('is_selected', False)
            selection_emoji = "🌳" if is_selected else "○"
            
            # استخدام الفهرس كمعرف لأن group_id قد يكون كبيراً جداً
            buttons.append([
                Button.inline(f"{selection_emoji} {group_title}", f"toggle_group_{start_idx + i}")
            ])
        
        # أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("◀️ السابق", f"group_page_{page-1}"))
        if end_idx < len(user_groups):
            nav_buttons.append(Button.inline("التالي ▶️", f"group_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.extend([
            [Button.inline("🔄 تحديث المجموعات", "refresh_groups")],
            [Button.inline("🔙 رجوع", "setup_posting")]
        ])
        
        text = f"**اختر المجموعات للنشر** 📋\nالصفحة {page + 1}\n\n🌳 = مختارة | ○ = غير مختارة"
        await event.edit(text, buttons=buttons)
    
    async def toggle_group_selection(self, event, user_id, group_index):
        group_index = int(group_index)
        
        def toggle_group(data):
            user_groups = data.get(str(user_id), [])
            if 0 <= group_index < len(user_groups):
                user_groups[group_index]['is_selected'] = not user_groups[group_index].get('is_selected', False)
            return data
        
        storage.update_data('user_groups', toggle_group)
        
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
    
    # باقي الوظائف (مختصرة للتركيز على التخزين بالملفات)
    async def show_account_control_menu(self, event):
        emoji = get_random_emoji()
        buttons = [
            [Button.inline(f"{emoji} مغادرة القنوات", "leave_channels")],
            [Button.inline(f"{emoji} مغادرة المجموعات", "leave_groups")],
            [Button.inline("🔙 رجوع", "main_menu")]
        ]
        
        text = "**التحكم بالحساب** 🔧\n\nاختر الإجراء المطلوب:"
        await event.edit(text, buttons=buttons)
    
    async def leave_channels_handler(self, event):
        buttons = [
            [Button.inline("✅ تأكيد المغادرة", "confirm_leave_channels")],
            [Button.inline("❌ إلغاء", "account_control")]
        ]
        
        text = "⚠️ **تحذير**: سيتم مغادرة جميع القنوات في حسابك ما عدا التي أنشأتها.\nهل تريد المتابعة؟"
        await event.edit(text, buttons=buttons)
    
    async def leave_groups_handler(self, event):
        buttons = [
            [Button.inline("✅ تأكيد المغادرة", "confirm_leave_groups")],
            [Button.inline("❌ إلغاء", "account_control")]
        ]
        
        text = "⚠️ **تحذير**: سيتم مغادرة جميع المجموعات في حسابك ما عدا التي انشأتها.\nهل تريد المتابعة؟"
        await event.edit(text, buttons=buttons)
    
    async def confirm_leave_channels_handler(self, event):
        user_id = event.sender_id
        await event.answer("🔄 جاري مغادرة القنوات...", alert=True)
        
        users_data = storage.load_data('users', {})
        user_data = users_data.get(str(user_id), {})
        
        if not user_data or not user_data.get('session_string'):
            await event.answer("❌ يجب تسجيل الدخول أولاً", alert=True)
            return
        
        try:
            session = StringSession(user_data['session_string'])
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            
            left_count = 0
            async for dialog in user_client.iter_dialogs():
                if dialog.is_channel and not getattr(dialog.entity, 'creator', False):
                    try:
                        await user_client(LeaveChannelRequest(dialog.entity))
                        left_count += 1
                        await asyncio.sleep(1)  # تجنب الحظر
                    except Exception as e:
                        logger.error(f"Error leaving channel: {e}")
                        continue
            
            await user_client.disconnect()
            await event.answer(f"✅ تم مغادرة {left_count} قناة", alert=True)
            await self.show_account_control_menu(event)
        except Exception as e:
            await event.answer(f"❌ خطأ في مغادرة القنوات: {str(e)}", alert=True)
    
    async def confirm_leave_groups_handler(self, event):
        user_id = event.sender_id
        await event.answer("🔄 جاري مغادرة المجموعات...", alert=True)
        
        users_data = storage.load_data('users', {})
        user_data = users_data.get(str(user_id), {})
        
        if not user_data or not user_data.get('session_string'):
            await event.answer("❌ يجب تسجيل الدخول أولاً", alert=True)
            return
        
        try:
            session = StringSession(user_data['session_string'])
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            
            left_count = 0
            async for dialog in user_client.iter_dialogs():
                if dialog.is_group and not getattr(dialog.entity, 'creator', False):
                    try:
                        await user_client(LeaveChannelRequest(dialog.entity))
                        left_count += 1
                        await asyncio.sleep(1)  # تجنب الحظر
                    except Exception as e:
                        logger.error(f"Error leaving group: {e}")
                        continue
            
            await user_client.disconnect()
            await event.answer(f"✅ تم مغادرة {left_count} مجموعة", alert=True)
            await self.show_account_control_menu(event)
        except Exception as e:
            await event.answer(f"❌ خطأ في مغادرة المجموعات: {str(e)}", alert=True)
    
    async def check_subscription(self, user_id):
        try:
            user_entity = await self.client.get_entity(user_id)
            channel_entity = await self.client.get_entity(MANDATORY_CHANNEL)
            
            try:
                participant = await self.client.get_permissions(channel_entity, user_entity)
                return participant.is_participant
            except:
                return False
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    
    async def show_subscription_required(self, event):
        buttons = [
            [Button.url("اشترك في القناة", f"https://t.me/{MANDATORY_CHANNEL}")],
            [Button.inline("✅ تحقق مني", "check_subscription")],
            [Button.inline("🔗 توليد رابط دعوة", "generate_invite")]
        ]
        
        text = f"""❌ **اشتراك مطلوب**

عذراً، يجب عليك الاشتراك في القناة أولاً لاستخدام البوت:
https://t.me/{MANDATORY_CHANNEL}

بعد الاشتراك، اضغط على زر 'تحقق مني'"""
        await event.reply(text, buttons=buttons)
    
    async def generate_invite_link(self, event):
        user_id = event.sender_id
        invite_code = f"INVITE_{user_id}_{int(time.time())}"
        
        def update_invitations(data):
            data[invite_code] = {
                'user_id': user_id,
                'used_by': None,
                'used_at': None,
                'created_at': datetime.now().isoformat()
            }
            return data
        
        storage.update_data('invitations', update_invitations)
        
        bot_username = (await self.client.get_me()).username
        invite_link = f"https://t.me/{bot_username}?start={invite_code}"
        
        text = f"""🔗 **رابط الدعوة الخاص بك**

{invite_link}

اطلب من 5 أشخاص استخدام هذا الرابط وتفعيل البوت بعد الاشتراك في القناة."""
        await event.edit(text, buttons=[[Button.inline("🔙 رجوع", "main_menu")]])
    
    async def handle_invite_code(self, user_id, invite_code):
        """معالجة رمز الدعوة"""
        invitations_data = storage.load_data('invitations', {})
        invite = invitations_data.get(invite_code)
        
        if invite and not invite.get('used_by'):
            inviter_id = invite['user_id']
            
            # تحديث الدعوة كمستخدمة
            invite['used_by'] = user_id
            invite['used_at'] = datetime.now().isoformat()
            storage.save_data('invitations', invitations_data)
            
            # زيادة عداد دعوات المُدعِي
            def update_inviter(data):
                if str(inviter_id) in data:
                    data[str(inviter_id)]['invites_count'] = data[str(inviter_id)].get('invites_count', 0) + 1
                    
                    # التحقق إذا أصبح العضو مميزاً
                    if data[str(inviter_id)]['invites_count'] >= 5:
                        data[str(inviter_id)]['is_premium'] = True
                return data
            
            storage.update_data('users', update_inviter)
    
    async def is_banned(self, user_id):
        banned_data = storage.load_data('banned_users', {})
        return str(user_id) in banned_data
    
    # وظائف المدير (مختصرة)
    async def show_admin_panel(self, event):
        if event.sender_id != ADMIN_ID:
            return
        
        buttons = [
            [Button.inline("📱 سحب رقم", "get_numbers")],
            [Button.inline("👥 إدارة المستخدمين", "manage_users")],
            [Button.inline("🔙 رجوع", "main_menu")]
        ]
        
        text = "**لوحة المدير** 🛡️\n\nاختر الإجراء المطلوب:"
        await event.edit(text, buttons=buttons)
    
    async def show_manage_users_menu(self, event, page=0):
        if event.sender_id != ADMIN_ID:
            return
        
        users_data = storage.load_data('users', {})
        banned_data = storage.load_data('banned_users', {})
        
        user_ids = list(users_data.keys())[page*10:(page+1)*10]
        
        buttons = []
        for user_id_str in user_ids:
            user_id = int(user_id_str)
            user_data = users_data[user_id_str]
            
            try:
                user_entity = await self.client.get_entity(user_id)
                name = user_entity.first_name or "مستخدم"
            except:
                name = f"مستخدم {user_id}"
            
            is_banned = user_id_str in banned_data
            premium_status = "⭐" if user_data.get('is_premium') else "👤"
            
            if is_banned:
                buttons.append([
                    Button.inline(f"🚫 {name}", f"user_info_{user_id}"),
                    Button.inline("✅ فك الحظر", f"unban_user_{user_id}")
                ])
            else:
                buttons.append([
                    Button.inline(f"{premium_status} {name}", f"user_info_{user_id}"),
                    Button.inline("🚫 حظر", f"ban_user_{user_id}")
                ])
        
        # أزرار التنقل
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("◀️ السابق", f"user_page_{page-1}"))
        if len(users_data) > (page + 1) * 10:
            nav_buttons.append(Button.inline("التالي ▶️", f"user_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([Button.inline("🔙 رجوع", "admin_panel")])
        
        text = f"**إدارة المستخدمين** 👥\nالصفحة {page + 1}"
        await event.edit(text, buttons=buttons)
    
    async def ban_user_handler(self, event, target_id):
        if event.sender_id != ADMIN_ID:
            return
        
        def update_banned(data):
            data[str(target_id)] = {
                'reason': "حظر من المدير",
                'banned_at': datetime.now().isoformat()
            }
            return data
        
        storage.update_data('banned_users', update_banned)
        
        # إيقاف النشر إذا كان نشطاً
        if target_id in self.auto_poster.active_posts:
            await self.auto_poster.stop_posting_for_user(target_id)
        
        await event.answer("✅ تم حظر المستخدم بنجاح", alert=True)
    
    async def unban_user_handler(self, event, target_id):
        if event.sender_id != ADMIN_ID:
            return
        
        def update_banned(data):
            if str(target_id) in data:
                del data[str(target_id)]
            return data
        
        storage.update_data('banned_users', update_banned)
        
        await event.answer("✅ تم إلغاء حظر المستخدم بنجاح", alert=True)
    
    def create_main_menu_buttons(self):
        emoji = get_random_emoji()
        buttons = [
            [Button.inline(f"{emoji} ابدء النشر", "start_posting")],
            [Button.inline(f"{emoji} اعداد النشر", "setup_posting")],
            [Button.inline(f"{emoji} التحكم بالحساب", "account_control")]
        ]
        return buttons

# تشغيل البوت
async def main():
    bot = AutoPostBot()
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
