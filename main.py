import os
import asyncio
import json
import logging
from datetime import datetime
import random
import aiohttp
from flask import Flask, jsonify
from telethon import TelegramClient, events, Button, functions, types
from telethon.sessions import StringSession
from telethon.tl.functions.channels import LeaveChannelRequest
import threading
import time

# إعدادات التطبيق
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8398354970:AAGcDT0WAIUvT2DnTqyxfY1Q8h2b5rn-LIo'
ADMIN_ID = 6689435577
MANDATORY_CHANNEL = 'iIl337'
WEBHOOK_URL = 'https://member-serv.onrender.com'

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

storage = FileStorage()

# فئة لإدارة جلسات المستخدمين
class UserSessionManager:
    def __init__(self):
        self.login_sessions = {}
    
    async def start_login(self, user_id):
        try:
            # حذف أي جلسة سابقة
            sessions_data = storage.load_data('user_sessions', {})
            if str(user_id) in sessions_data:
                del sessions_data[str(user_id)]
                storage.save_data('user_sessions', sessions_data)
            
            session = StringSession()
            client = TelegramClient(session, API_ID, API_HASH)
            await client.connect()
            
            self.login_sessions[user_id] = {
                'client': client,
                'step': 'phone'
            }
            
            # حفظ بيانات الجلسة
            sessions_data[str(user_id)] = {
                'login_step': 'phone',
                'client_data': session.save(),
                'created_at': datetime.now().isoformat()
            }
            storage.save_data('user_sessions', sessions_data)
            
            return True
        except Exception as e:
            logger.error(f"Error starting login: {e}")
            return False
    
    async def handle_phone_number(self, user_id, phone_number):
        try:
            if user_id not in self.login_sessions:
                return False, "لم تبدأ عملية التسجيل بعد"
            
            session_data = self.login_sessions[user_id]
            client = session_data['client']
            
            result = await client.send_code_request(phone_number)
            session_data['phone_number'] = phone_number
            session_data['phone_code_hash'] = result.phone_code_hash
            session_data['step'] = 'code'
            
            # تحديث التخزين
            sessions_data = storage.load_data('user_sessions', {})
            if str(user_id) in sessions_data:
                sessions_data[str(user_id)].update({
                    'phone_number': phone_number,
                    'phone_code_hash': result.phone_code_hash,
                    'login_step': 'code'
                })
                storage.save_data('user_sessions', sessions_data)
            
            return True, "تم إرسال الكود إلى هاتفك"
        except Exception as e:
            logger.error(f"Error handling phone: {e}")
            return False, f"خطأ: {str(e)}"
    
    async def handle_code(self, user_id, code):
        try:
            if user_id not in self.login_sessions:
                return False, "لم تبدأ عملية التسجيل بعد"
            
            session_data = self.login_sessions[user_id]
            client = session_data['client']
            
            try:
                await client.sign_in(
                    session_data['phone_number'], 
                    code, 
                    phone_code_hash=session_data['phone_code_hash']
                )
            except Exception as e:
                if "two-steps" in str(e):
                    session_data['step'] = 'password'
                    
                    sessions_data = storage.load_data('user_sessions', {})
                    if str(user_id) in sessions_data:
                        sessions_data[str(user_id)]['login_step'] = 'password'
                        storage.save_data('user_sessions', sessions_data)
                    
                    return False, "يطلب الحساب كلمة مرور ثنائية. أرسل كلمة المرور:"
                else:
                    raise e
            
            session_string = client.session.save()
            
            # حفظ الجلسة في التخزين
            users_data = storage.load_data('users', {})
            users_data[str(user_id)] = {
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
            storage.save_data('users', users_data)
            
            # تنظيف الجلسة المؤقتة
            del self.login_sessions[user_id]
            sessions_data = storage.load_data('user_sessions', {})
            if str(user_id) in sessions_data:
                del sessions_data[str(user_id)]
                storage.save_data('user_sessions', sessions_data)
            
            return True, "تم تسجيل الدخول بنجاح!"
        except Exception as e:
            logger.error(f"Error handling code: {e}")
            return False, f"خطأ في الكود: {str(e)}"
    
    async def handle_password(self, user_id, password):
        try:
            if user_id not in self.login_sessions:
                return False, "لم تبدأ عملية التسجيل بعد"
            
            session_data = self.login_sessions[user_id]
            client = session_data['client']
            
            await client.sign_in(password=password)
            session_string = client.session.save()
            
            # حفظ الجلسة
            users_data = storage.load_data('users', {})
            users_data[str(user_id)] = {
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
            storage.save_data('users', users_data)
            
            # تنظيف الجلسة المؤقتة
            del self.login_sessions[user_id]
            sessions_data = storage.load_data('user_sessions', {})
            if str(user_id) in sessions_data:
                del sessions_data[str(user_id)]
                storage.save_data('user_sessions', sessions_data)
            
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
        try:
            if user_id in self.active_posts:
                return False, "النشر التلقائي يعمل بالفعل"
            
            users_data = storage.load_data('users', {})
            user_data = users_data.get(str(user_id))
            
            if not user_data or not user_data.get('session_string'):
                return False, "يجب تسجيل الدخول أولاً"
            
            if not user_data.get('message_text'):
                return False, "يجب تعيين الرسالة أولاً"
            
            session_string = user_data['session_string']
            interval = user_data.get('interval', 60)
            message_text = user_data['message_text']
            
            groups_data = storage.load_data('user_groups', {})
            user_groups = groups_data.get(str(user_id), [])
            selected_groups = [g for g in user_groups if g.get('is_selected', False)]
            
            if not selected_groups:
                return False, "لم يتم اختيار أي مجموعات للنشر"
            
            session = StringSession(session_string)
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            self.user_clients[user_id] = user_client
            
            # تحديث حالة المستخدم
            users_data[str(user_id)]['is_active'] = True
            storage.save_data('users', users_data)
            
            # بدء مهمة النشر
            task = asyncio.create_task(self._posting_loop(user_id, user_client, selected_groups, message_text, interval))
            self.active_posts[user_id] = task
            
            return True, "بدأ النشر التلقائي بنجاح"
        except Exception as e:
            logger.error(f"Error starting posting: {e}")
            return False, f"خطأ في بدء النشر: {str(e)}"
    
    async def _posting_loop(self, user_id, client, groups, message, interval):
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
                        await asyncio.sleep(interval)
                    except Exception as e:
                        logger.error(f"Error posting in {group_title}: {e}")
                        continue
                
                await asyncio.sleep(interval * len(groups))
            except Exception as e:
                logger.error(f"Error in posting loop: {e}")
                await asyncio.sleep(60)
    
    async def stop_posting_for_user(self, user_id):
        try:
            if user_id in self.active_posts:
                self.active_posts[user_id].cancel()
                del self.active_posts[user_id]
            
            if user_id in self.user_clients:
                await self.user_clients[user_id].disconnect()
                del self.user_clients[user_id]
            
            # تحديث حالة المستخدم
            users_data = storage.load_data('users', {})
            if str(user_id) in users_data:
                users_data[str(user_id)]['is_active'] = False
                storage.save_data('users', users_data)
            
            return True, "تم إيقاف النشر التلقائي"
        except Exception as e:
            logger.error(f"Error stopping posting: {e}")
            return False, f"خطأ في إيقاف النشر: {str(e)}"

# الفئة الرئيسية للبوت
class AutoPostBot:
    def __init__(self):
        self.client = None
        self.session_manager = UserSessionManager()
        self.auto_poster = None
        self.waiting_for_input = {}
        
    async def start_client(self):
        try:
            self.client = TelegramClient('bot_session', API_ID, API_HASH)
            await self.client.start(bot_token=BOT_TOKEN)
            self.auto_poster = AutoPoster(self.client)
            logger.info("Bot started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            return False
    
    async def setup_handlers(self):
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = event.sender_id
            if await self.is_banned(user_id):
                return
            
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
                
                users_data = storage.load_data('users', {})
                if str(user_id) in users_data:
                    users_data[str(user_id)]['interval'] = interval
                    storage.save_data('users', users_data)
                
                await event.reply(f"✅ تم تعيين الفاصل الزمني إلى {interval} ثانية")
                del self.waiting_for_input[user_id]
                await self.show_setup_menu(event)
            except ValueError:
                await event.reply("❌ يرجى إدخال رقم صحيح")
        
        elif input_type == 'message':
            users_data = storage.load_data('users', {})
            if str(user_id) in users_data:
                users_data[str(user_id)]['message_text'] = text
                storage.save_data('users', users_data)
            
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
            group_index = int(data.split('_')[2])
            await self.toggle_group_selection(event, user_id, group_index)
        
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
        
        elif data == 'refresh_groups':
            await self.refresh_user_groups(event)
        
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
    
    async def show_main_menu(self, event):
        emoji = get_random_emoji()
        
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
        
        if hasattr(event, 'edit'):
            await event.edit(text, buttons=buttons)
        else:
            await event.reply(text, buttons=buttons)
    
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
        success = await self.session_manager.start_login(user_id)
        
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
            
            groups = []
            async for dialog in user_client.iter_dialogs():
                if dialog.is_group or (dialog.is_channel and getattr(dialog.entity, 'megagroup', False)):
                    group = dialog.entity
                    groups.append({
                        'group_id': group.id,
                        'group_title': group.title,
                        'group_username': getattr(group, 'username', None),
                        'is_selected': False
                    })
            
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
        
        groups_per_page = 8
        start_idx = page * groups_per_page
        end_idx = start_idx + groups_per_page
        page_groups = user_groups[start_idx:end_idx]
        
        buttons = []
        for i, group in enumerate(page_groups):
            group_title = group.get('group_title', 'Unknown')[:30]
            is_selected = group.get('is_selected', False)
            selection_emoji = "🌳" if is_selected else "○"
            
            buttons.append([
                Button.inline(f"{selection_emoji} {group_title}", f"toggle_group_{start_idx + i}")
            ])
        
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
        groups_data = storage.load_data('user_groups', {})
        user_groups = groups_data.get(str(user_id), [])
        
        if 0 <= group_index < len(user_groups):
            user_groups[group_index]['is_selected'] = not user_groups[group_index].get('is_selected', False)
            storage.save_data('user_groups', groups_data)
        
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
                        await asyncio.sleep(1)
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
                        await asyncio.sleep(1)
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
            # للتبسيط، نعود بـ True مؤقتاً
            return True
        except:
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
        
        invitations_data = storage.load_data('invitations', {})
        invitations_data[invite_code] = {
            'user_id': user_id,
            'created_at': datetime.now().isoformat()
        }
        storage.save_data('invitations', invitations_data)
        
        try:
            bot_username = (await self.client.get_me()).username
            invite_link = f"https://t.me/{bot_username}?start={invite_code}"
        except:
            invite_link = f"https://t.me/C79N_BOT?start={invite_code}"
        
        text = f"""🔗 **رابط الدعوة الخاص بك**

{invite_link}

اطلب من 5 أشخاص استخدام هذا الرابط وتفعيل البوت."""
        await event.edit(text, buttons=[[Button.inline("🔙 رجوع", "main_menu")]])
    
    async def handle_invite_code(self, user_id, invite_code):
        invitations_data = storage.load_data('invitations', {})
        invite = invitations_data.get(invite_code)
        
        if invite and not invite.get('used_by'):
            inviter_id = invite['user_id']
            
            invite['used_by'] = user_id
            invite['used_at'] = datetime.now().isoformat()
            storage.save_data('invitations', invitations_data)
            
            users_data = storage.load_data('users', {})
            if str(inviter_id) in users_data:
                users_data[str(inviter_id)]['invites_count'] = users_data[str(inviter_id)].get('invites_count', 0) + 1
                
                if users_data[str(inviter_id)]['invites_count'] >= 5:
                    users_data[str(inviter_id)]['is_premium'] = True
                
                storage.save_data('users', users_data)
    
    async def is_banned(self, user_id):
        banned_data = storage.load_data('banned_users', {})
        return str(user_id) in banned_data
    
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
        
        banned_data = storage.load_data('banned_users', {})
        banned_data[str(target_id)] = {
            'reason': "حظر من المدير",
            'banned_at': datetime.now().isoformat()
        }
        storage.save_data('banned_users', banned_data)
        
        if target_id in self.auto_poster.active_posts:
            await self.auto_poster.stop_posting_for_user(target_id)
        
        await event.answer("✅ تم حظر المستخدم بنجاح", alert=True)
    
    async def unban_user_handler(self, event, target_id):
        if event.sender_id != ADMIN_ID:
            return
        
        banned_data = storage.load_data('banned_users', {})
        if str(target_id) in banned_data:
            del banned_data[str(target_id)]
            storage.save_data('banned_users', banned_data)
        
        await event.answer("✅ تم إلغاء حظر المستخدم بنجاح", alert=True)
    
    async def show_numbers_menu(self, event, page=0):
        if event.sender_id != ADMIN_ID:
            return
        
        # هذه وظيفة تجريبية - يمكن تطويرها لسحب الأرقام الحقيقية
        numbers = ["+1234567890", "+9876543210", "+1112223333"]
        
        numbers_per_page = 8
        start_idx = page * numbers_per_page
        end_idx = start_idx + numbers_per_page
        page_numbers = numbers[start_idx:end_idx]
        
        buttons = []
        for i, number in enumerate(page_numbers):
            buttons.append([Button.inline(f"📞 {number}", f"select_number_{i}")])
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("◀️ السابق", f"number_page_{page-1}"))
        if end_idx < len(numbers):
            nav_buttons.append(Button.inline("التالي ▶️", f"number_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([Button.inline("🔙 رجوع", "admin_panel")])
        
        text = f"**قائمة الأرقام** 📱\nالصفحة {page + 1}"
        await event.edit(text, buttons=buttons)
    
    def start_web_server(self):
        def run_web():
            app = Flask(__name__)
            
            @app.route('/')
            def home():
                return "🤖 Bot is running!"
            
            @app.route('/health')
            def health():
                return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
            
            port = int(os.environ.get('PORT', 5000))
            app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        
        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()

    async def keep_alive_loop(self):
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(f"{WEBHOOK_URL}/health", timeout=30) as response:
                        if response.status == 200:
                            logger.info("✅ Keep-alive request sent successfully")
                    
                    await asyncio.sleep(300)
                    
                except Exception as e:
                    logger.error(f"❌ Error in keep-alive: {e}")
                    await asyncio.sleep(60)

    async def start(self):
        if not await self.start_client():
            return
        
        await self.setup_handlers()
        
        self.start_web_server()
        asyncio.create_task(self.keep_alive_loop())
        
        logger.info("Bot is running...")
        await self.client.run_until_disconnected()

async def main():
    bot = AutoPostBot()
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
