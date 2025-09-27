import os
import asyncio
import json
import logging
from datetime import datetime
import random
import httpx
from flask import Flask, jsonify
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
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
            'banned_users': 'banned_users.json'
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

# الفئة الرئيسية للبوت
class AutoPostBot:
    def __init__(self):
        self.client = None
        self.waiting_for_input = {}
        self.login_sessions = {}
        
    async def start_client(self):
        try:
            self.client = TelegramClient('bot_session', API_ID, API_HASH)
            await self.client.start(bot_token=BOT_TOKEN)
            logger.info("✅ Bot started successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
            return False
    
    async def setup_handlers(self):
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = event.sender_id
            if await self.is_banned(user_id):
                return
            
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
                await self.handle_user_input(event)
        
        @self.client.on(events.CallbackQuery)
        async def callback_handler(event):
            user_id = event.sender_id
            if await self.is_banned(user_id):
                return
            
            data = event.data.decode('utf-8')
            await self.handle_callback(event, data)
    
    async def handle_user_input(self, event):
        user_id = event.sender_id
        text = event.text
        input_type = self.waiting_for_input[user_id]['type']
        
        if input_type == 'interval':
            try:
                interval = int(text)
                if interval < 10:
                    await event.reply("❌ الفاصل الزمني يجب أن يكون 10 ثواني على الأقل")
                    return
                
                users_data = storage.load_data('users', {})
                if str(user_id) not in users_data:
                    users_data[str(user_id)] = {}
                users_data[str(user_id)]['interval'] = interval
                storage.save_data('users', users_data)
                
                await event.reply(f"✅ تم تعيين الفاصل الزمني إلى {interval} ثانية")
                del self.waiting_for_input[user_id]
            except ValueError:
                await event.reply("❌ يرجى إدخال رقم صحيح")
        
        elif input_type == 'message':
            users_data = storage.load_data('users', {})
            if str(user_id) not in users_data:
                users_data[str(user_id)] = {}
            users_data[str(user_id)]['message_text'] = text
            storage.save_data('users', users_data)
            
            await event.reply("✅ تم حفظ الرسالة بنجاح")
            del self.waiting_for_input[user_id]
    
    async def handle_callback(self, event, data):
        user_id = event.sender_id
        
        if data == 'main_menu':
            await self.show_main_menu(event)
        
        elif data == 'start_posting':
            await self.start_posting_handler(event)
        
        elif data == 'setup_posting':
            await self.show_setup_menu(event)
        
        elif data == 'set_interval':
            await self.set_interval_handler(event)
        
        elif data == 'set_message':
            await self.set_message_handler(event)
        
        elif data == 'check_subscription':
            if await self.check_subscription(user_id):
                await self.show_main_menu(event)
            else:
                await event.answer("❌ لم تشترك بعد في القناة!", alert=True)
        
        elif data == 'generate_invite':
            await self.generate_invite_link(event)
        
        elif user_id == ADMIN_ID and data == 'admin_panel':
            await self.show_admin_panel(event)
    
    async def show_main_menu(self, event):
        emoji = get_random_emoji()
        buttons = [
            [Button.inline(f"{emoji} ابدء النشر", "start_posting")],
            [Button.inline(f"{emoji} اعداد النشر", "setup_posting")],
            [Button.inline(f"{emoji} التحكم بالحساب", "account_control")]
        ]
        
        if event.sender_id == ADMIN_ID:
            buttons.append([Button.inline("🛡️ لوحة المدير", "admin_panel")])
        
        text = "**مرحبا بك في بوت النشر التلقائي** 🌟\n\nاختر الإجراء المطلوب:"
        
        if hasattr(event, 'edit'):
            await event.edit(text, buttons=buttons)
        else:
            await event.reply(text, buttons=buttons)
    
    async def show_setup_menu(self, event):
        emoji = get_random_emoji()
        buttons = [
            [Button.inline(f"{emoji} تعيين الفاصل", "set_interval")],
            [Button.inline(f"{emoji} تعيين الرسالة", "set_message")],
            [Button.inline("🔙 رجوع", "main_menu")]
        ]
        
        text = "**إعدادات النشر** ⚙️\n\nقم بتعيين الإعدادات المطلوبة:"
        await event.edit(text, buttons=buttons)
    
    async def set_interval_handler(self, event):
        user_id = event.sender_id
        self.waiting_for_input[user_id] = {'type': 'interval'}
        await event.answer("أدخل الفاصل الزمني بين الرسائل (بالثواني):", alert=True)
    
    async def set_message_handler(self, event):
        user_id = event.sender_id
        self.waiting_for_input[user_id] = {'type': 'message'}
        await event.answer("أدخل نص الرسالة التي تريد نشرها:", alert=True)
    
    async def start_posting_handler(self, event):
        user_id = event.sender_id
        users_data = storage.load_data('users', {})
        user_data = users_data.get(str(user_id), {})
        
        if not user_data.get('message_text'):
            await event.answer("❌ يجب تعيين الرسالة أولاً!", alert=True)
            return
        
        await event.answer("✅ بدأ النشر التلقائي...", alert=True)
    
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
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    response = await client.get(f"{WEBHOOK_URL}/health", timeout=30)
                    if response.status_code == 200:
                        logger.info("✅ Keep-alive request sent successfully")
                    else:
                        logger.warning(f"⚠️ Keep-alive request failed: {response.status_code}")
                    
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
        
        logger.info("🚀 Bot is running and ready...")
        await self.client.run_until_disconnected()

async def main():
    # التحقق من تثبيت المكتبات أولاً
    try:
        import telethon
        import flask
        import httpx
        logger.info("✅ All imports successful")
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return
    
    bot = AutoPostBot()
    await bot.start()

if __name__ == '__main__':
    asyncio.run(main())
