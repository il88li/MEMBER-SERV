import os
import json
import random
import asyncio
import threading
from telethon import TelegramClient, errors
from telethon.tl.types import User, InputPhoneContact
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.functions.channels import InviteToChannelRequest
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# بيانات API
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8390052181:AAH9q_7rgJd2jcvtT3yMb2cFo6667piyJsw'

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN)

# تهيئة Telethon client
client = TelegramClient('user_session', API_ID, API_HASH)

# ملفات البيانات
DATA_FILE = 'user_data.json'
SETTINGS_FILE = 'settings.json'
PROCESS_FILE = 'process_status.json'

# تحميل البيانات
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def load_process_status():
    try:
        with open(PROCESS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_process_status(status):
    with open(PROCESS_FILE, 'w') as f:
        json.dump(status, f, indent=4)

# إنشاء الأزرار
def main_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 1
    keyboard.add(
        InlineKeyboardButton("🚀 بدء العملية", callback_data="start_process"),
        InlineKeyboardButton("🔐 تسجيل | ⚙️ إعدادات", callback_data="login_settings"),
        InlineKeyboardButton("📊 إحصائيات العملية الحالية", callback_data="stats")
    )
    return keyboard

def login_settings_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 2
    keyboard.add(
        InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login"),
        InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
    )
    keyboard.add(InlineKeyboardButton("🔙 العودة", callback_data="main_menu"))
    return keyboard

def settings_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 1
    keyboard.add(
        InlineKeyboardButton("📥 تعيين المجموعة المصدر", callback_data="set_source"),
        InlineKeyboardButton("📤 تعيين المجموعة الهدف", callback_data="set_target"),
        InlineKeyboardButton("🔢 تعيين عدد الأعضاء", callback_data="set_count"),
        InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_process"),
        InlineKeyboardButton("🔙 العودة", callback_data="main_menu")
    )
    return keyboard

# معالجة الأوامر
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = """
╔══════════════════════╗
    🚀 **بوت إضافة الأعضاء المتقدم**  
╚══════════════════════╝

🎯 *المميزات:*
• 📥 جلب الأعضاء من مجموعات مصدر  
• 📤 إضافة تلقائية للمجموعات الهدف  
• 🛡️ نظام فلترة متقدم  
• 📊 إحصائيات حية  

👆 *اختر أحد الخيارات أدناه للبدء:*
    """
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = str(call.from_user.id)
    data = load_data()
    
    if call.data == "main_menu":
        menu_text = """
╔══════════════════════╗
       📋 **القائمة الرئيسية**  
╚══════════════════════╝

👆 *اختر الإجراء المطلوب:*
        """
        bot.edit_message_text(menu_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=main_menu())
    
    elif call.data == "login_settings":
        login_settings_text = """
╔══════════════════════╗
       🔐 **التسجيل والإعدادات**  
╚══════════════════════╝

⚡ *إعدادات الحساب والإضافة:*
• 🔐 تسجيل الدخول بالحساب  
• ⚙️ ضبط إعدادات العملية  

👇 *اختر الخيار المناسب:*
        """
        bot.edit_message_text(login_settings_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=login_settings_menu())
    
    elif call.data == "start_process":
        if user_id not in data or not data[user_id].get('logged_in', False):
            bot.answer_callback_query(call.id, "❌ يجب تسجيل الدخول أولاً!")
            return
        
        settings = load_settings()
        if user_id not in settings or not settings[user_id].get('source') or not settings[user_id].get('target'):
            bot.answer_callback_query(call.id, "❌ يجب تعيين الإعدادات أولاً!")
            return
        
        process_text = """
╔══════════════════════╗
       🚀 **بدء العملية**  
╚══════════════════════╝

⚡ *جاري بدء عملية الإضافة...*
⏳ *قد تستغرق عدة دقائق*
🛡️ *النظام يعمل تلقائياً*
        """
        bot.edit_message_text(process_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.answer_callback_query(call.id, "🚀 بدأت العملية...")
        threading.Thread(target=run_async_process, args=(user_id, call.message)).start()
    
    elif call.data == "login":
        if user_id in data and data[user_id].get('logged_in', False):
            bot.answer_callback_query(call.id, "✅ مسجل بالفعل!")
            return
        
        login_text = """
╔══════════════════════╗
       🔐 **تسجيل الدخول**  
╚══════════════════════╝

📞 *أرسل رقم الهاتف مع رمز الدولة:*
🌍 *مثال: +201234567890*
        """
        msg = bot.send_message(call.message.chat.id, login_text, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_phone)
    
    elif call.data == "settings":
        settings_text = """
╔══════════════════════╗
       ⚙️ **الإعدادات**  
╚══════════════════════╝

🔧 *إعدادات عملية الإضافة:*
• 📥 مصدر الأعضاء  
• 📤 المجموعة الهدف  
• 🔢 عدد الأعضاء  

👇 *اختر الإعداد المطلوب:*
        """
        bot.edit_message_text(settings_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=settings_menu())
    
    elif call.data == "stats":
        show_stats(call.message, user_id)
    
    elif call.data == "set_source":
        source_text = """
╔══════════════════════╗
       📥 **المجموعة المصدر**  
╚══════════════════════╝

📌 *أرسل رابط أو معرف المجموعة:*
• 🔗 الرابط: https://t.me/groupname  
• 🆔 المعرف: @groupname  
        """
        msg = bot.send_message(call.message.chat.id, source_text, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_source, user_id)
    
    elif call.data == "set_target":
        target_text = """
╔══════════════════════╗
       📤 **المجموعة الهدف**  
╚══════════════════════╝

📌 *أرسل رابط أو معرف المجموعة:*
• 🔗 الرابط: https://t.me/groupname  
• 🆔 المعرف: @groupname  
• 📢 يمكن أن تكون قناة  
        """
        msg = bot.send_message(call.message.chat.id, target_text, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_target, user_id)
    
    elif call.data == "set_count":
        count_text = """
╔══════════════════════╗
       🔢 **عدد الأعضاء**  
╚══════════════════════╝

🔢 *أرسل عدد الأعضاء المطلوب:*
• 📊 العدد الموصى به: 50-100  
• ⚠️ تجنب الأعداد الكبيرة  
        """
        msg = bot.send_message(call.message.chat.id, count_text, parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_count, user_id)
    
    elif call.data == "cancel_process":
        cancel_process(user_id, call.message)

def process_phone(message):
    user_id = str(message.from_user.id)
    data = load_data()
    
    if user_id not in data:
        data[user_id] = {}
    
    data[user_id]['phone'] = message.text
    save_data(data)
    
    password_text = """
╔══════════════════════╗
       🔑 **كلمة المرور**  
╚══════════════════════╝

🔒 *أرسل كلمة المرور:*
• 🔐 سيتم تشفير البيانات  
• 🛡️ آمن تماماً  
        """
    msg = bot.send_message(message.chat.id, password_text, parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_password)

def process_password(message):
    user_id = str(message.from_user.id)
    data = load_data()
    
    data[user_id]['password'] = message.text
    save_data(data)
    
    # محاولة تسجيل الدخول
    asyncio.run(login_user(user_id, message))

async def login_user(user_id, message):
    data = load_data()
    user_data = data[user_id]
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(user_data['phone'])
            await client.sign_in(user_data['phone'], user_data['password'])
        
        user_data['logged_in'] = True
        save_data(data)
        
        success_text = """
╔══════════════════════╗
       ✅ **تم التسجيل**  
╚══════════════════════╝

🎉 *تم تسجيل الدخول بنجاح!*
⚡ *يمكنك الآن بدء العملية*
        """
        bot.send_message(message.chat.id, success_text, parse_mode='Markdown', reply_markup=main_menu())
    except Exception as e:
        error_text = f"""
╔══════════════════════╗
       ❌ **خطأ في التسجيل**  
╚══════════════════════╝

⚠️ *فشل في تسجيل الدخول:*
`{str(e)}`

🔧 *حاول مرة أخرى:*
        """
        bot.send_message(message.chat.id, error_text, parse_mode='Markdown', reply_markup=main_menu())

def process_source(message, user_id):
    settings = load_settings()
    
    if user_id not in settings:
        settings[user_id] = {}
    
    settings[user_id]['source'] = message.text
    save_settings(settings)
    
    success_text = """
╔══════════════════════╗
       ✅ **تم الحفظ**  
╚══════════════════════╝

📥 *تم حفظ المجموعة المصدر:*
`{}`

⚡ *يمكنك تعديلها لاحقاً*
    """.format(message.text)
    bot.send_message(message.chat.id, success_text, parse_mode='Markdown', reply_markup=main_menu())

def process_target(message, user_id):
    settings = load_settings()
    
    if user_id not in settings:
        settings[user_id] = {}
    
    settings[user_id]['target'] = message.text
    save_settings(settings)
    
    success_text = """
╔══════════════════════╗
       ✅ **تم الحفظ**  
╚══════════════════════╝

📤 *تم حفظ المجموعة الهدف:*
`{}`

⚡ *يمكنك تعديلها لاحقاً*
    """.format(message.text)
    bot.send_message(message.chat.id, success_text, parse_mode='Markdown', reply_markup=main_menu())

def process_count(message, user_id):
    settings = load_settings()
    
    try:
        count = int(message.text)
        if user_id not in settings:
            settings[user_id] = {}
        
        settings[user_id]['count'] = count
        save_settings(settings)
        
        success_text = """
╔══════════════════════╗
       ✅ **تم التعيين**  
╚══════════════════════╝

🔢 *تم تعيين عدد الأعضاء:*
`{}`

⚡ *سيتم العمل بهذا العدد*
        """.format(count)
        bot.send_message(message.chat.id, success_text, parse_mode='Markdown', reply_markup=main_menu())
    except ValueError:
        error_text = """
╔══════════════════════╗
       ❌ **خطأ في الإدخال**  
╚══════════════════════╝

⚠️ *الرجاء إدخال رقم صحيح*
🔢 *مثال: 50*
        """
        bot.send_message(message.chat.id, error_text, parse_mode='Markdown')

def show_stats(message, user_id):
    settings = load_settings()
    process_status = load_process_status()
    user_settings = settings.get(user_id, {})
    user_process = process_status.get(user_id, {})
    
    status_emoji = {
        'جاري العمل': '🟡',
        'مكتمل': '🟢',
        'ملغى': '🔴',
        'غير نشط': '⚪',
        'خطأ': '🔴'
    }.get(user_process.get('status', 'غير نشط'), '⚪')
    
    stats_text = f"""
╔══════════════════════╗
       📊 **الإحصائيات**  
╚══════════════════════╝

📥 **المصدر:** `{user_settings.get('source', 'غير معين')}`
📤 **الهدف:** `{user_settings.get('target', 'غير معين')}`
🔢 **العدد المطلوب:** `{user_settings.get('count', 'غير معين')}`

📈 **حالة العملية:**
{status_emoji} **الحالة:** {user_process.get('status', 'غير نشط')}
🔢 **تم معالجة:** `{user_process.get('processed', 0)}` عضو
✅ **تم الإضافة:** `{user_process.get('added', 0)}` عضو
❌ **فشل الإضافة:** `{user_process.get('failed', 0)}` عضو

⚡ *آخر تحديث للبيانات*
    """
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

def cancel_process(user_id, message):
    process_status = load_process_status()
    if user_id in process_status:
        process_status[user_id]['cancelled'] = True
        save_process_status(process_status)
        
        success_text = """
╔══════════════════════╗
       ✅ **تم الإلغاء**  
╚══════════════════════╝

🛑 *تم إلغاء العملية بنجاح*
⚡ *يمكنك البدء بعملية جديدة*
        """
        bot.send_message(message.chat.id, success_text, parse_mode='Markdown')
    else:
        error_text = """
╔══════════════════════╗
       ℹ️ **لا يوجد عملية**  
╚══════════════════════╝

📭 *لا توجد عملية نشطة للإلغاء*
🚀 *يمكنك بدء عملية جديدة*
        """
        bot.send_message(message.chat.id, error_text, parse_mode='Markdown')

def run_async_process(user_id, message):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_process(user_id, message))
    loop.close()

async def start_process(user_id, message):
    settings = load_settings()
    user_settings = settings.get(user_id, {})
    
    source = user_settings.get('source')
    target = user_settings.get('target')
    count = user_settings.get('count', 50)
    
    if not source or not target:
        error_text = """
╔══════════════════════╗
       ❌ **إعدادات ناقصة**  
╚══════════════════════╝

⚠️ *الإعدادات غير مكتملة!*
🔧 *يرجى تعيين المصدر والهدف*
        """
        bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
        return
    
    # تحديث حالة العملية
    process_status = load_process_status()
    if user_id not in process_status:
        process_status[user_id] = {}
    process_status[user_id].update({
        'status': 'جاري العمل',
        'processed': 0,
        'added': 0,
        'failed': 0,
        'cancelled': False
    })
    save_process_status(process_status)
    
    try:
        # جلب الأعضاء من المصدر
        progress_text = """
╔══════════════════════╗
       🔍 **جاري البحث**  
╚══════════════════════╝

🔎 *جاري جلب الأعضاء من المصدر...*
⏳ *قد يستغرق بضع دقائق*
        """
        bot.send_message(message.chat.id, progress_text, parse_mode='Markdown')
        
        members = await get_filtered_members(source, count, user_id)
        
        if not members:
            error_text = """
╔══════════════════════╗
       ℹ️ **لا يوجد أعضاء**  
╚══════════════════════╝

🔍 *لم يتم العثور على أعضاء مناسبين!*
⚙️ *جرب تغيير إعدادات الفلترة*
            """
            bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
            process_status[user_id]['status'] = 'مكتمل - لا يوجد أعضاء'
            save_process_status(process_status)
            return
        
        # تحديث الإحصائيات
        process_status[user_id]['processed'] = len(members)
        save_process_status(process_status)
        
        # إضافة إلى جهات الاتصال
        contacts_text = f"""
╔══════════════════════╗
       📞 **إضافة جهات**  
╚══════════════════════╝

📞 *جاري إضافة جهات الاتصال...*
🔢 *العدد: {len(members)} عضو*
        """
        bot.send_message(message.chat.id, contacts_text, parse_mode='Markdown')
        
        added_contacts = await add_to_contacts(members, user_id)
        
        if process_status[user_id].get('cancelled', False):
            cancelled_text = """
╔══════════════════════╗
       🛑 **تم الإلغاء**  
╚══════════════════════╝

❌ *تم إلغاء العملية من قبل المستخدم*
⚡ *يمكنك البدء من جديد*
            """
            bot.send_message(message.chat.id, cancelled_text, parse_mode='Markdown')
            process_status[user_id]['status'] = 'ملغى'
            save_process_status(process_status)
            return
        
        # إضافة إلى المجموعة الهدف
        target_text = f"""
╔══════════════════════╗
       ➡️ **الإضافة للهدف**  
╚══════════════════════╝

📤 *جاري الإضافة إلى المجموعة الهدف...*
🔢 *العدد: {len(added_contacts)} عضو*
⏳ *قد يستغرق عدة دقائق*
        """
        bot.send_message(message.chat.id, target_text, parse_mode='Markdown')
        
        added_to_group = await add_to_target(target, added_contacts, user_id)
        
        # تحديث الإحصائيات النهائية
        process_status[user_id]['added'] = len(added_to_group)
        process_status[user_id]['failed'] = len(added_contacts) - len(added_to_group)
        process_status[user_id]['status'] = 'مكتمل'
        save_process_status(process_status)
        
        # إحصائيات
        success_text = f"""
╔══════════════════════╗
       ✅ **اكتملت العملية**  
╚══════════════════════╝

📊 **نتائج العملية:**
🔢 **تم معالجة:** `{len(members)}` عضو
✅ **تم الإضافة:** `{len(added_to_group)}` عضو
❌ **فشل الإضافة:** `{len(added_contacts) - len(added_to_group)}` عضو

🎉 *تمت العملية بنجاح!*
        """
        bot.send_message(message.chat.id, success_text, parse_mode='Markdown')
        
    except Exception as e:
        error_text = f"""
╔══════════════════════╗
       ❌ **حدث خطأ**  
╚══════════════════════╝

⚠️ *حدث خطأ أثناء العملية:*
`{str(e)}`

🔧 *جاري استعادة النظام...*
        """
        bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
        process_status[user_id]['status'] = f'خطأ: {str(e)}'
        save_process_status(process_status)

async def get_filtered_members(source, count, user_id):
    try:
        entity = await client.get_entity(source)
        all_members = await client.get_participants(entity, limit=count * 3)
        
        filtered_members = []
        
        settings = load_settings()
        user_settings = settings.get(user_id, {})
        target = user_settings.get('target')
        target_members = []
        
        if target:
            try:
                target_entity = await client.get_entity(target)
                target_members = await client.get_participants(target_entity, limit=100)
            except:
                pass
        
        target_user_ids = [m.id for m in target_members]
        
        for member in all_members:
            if len(filtered_members) >= count:
                break
                
            if await is_valid_member(member, target_user_ids):
                filtered_members.append(member)
        
        return filtered_members
    except Exception as e:
        print(f"Error getting members: {e}")
        return []

async def is_valid_member(member, target_user_ids):
    if member.bot:
        return False
    
    if getattr(member, 'deleted', False):
        return False
    
    try:
        participant = getattr(member, 'participant', None)
        if participant and getattr(participant, 'admin_rights', None):
            return False
    except:
        pass
    
    if member.id in target_user_ids:
        return False
    
    if not getattr(member, 'phone', None):
        return False
    
    return True

async def add_to_contacts(members, user_id):
    contacts = []
    added = []
    
    process_status = load_process_status()
    
    for member in members:
        if process_status.get(user_id, {}).get('cancelled', False):
            break
            
        if isinstance(member, User) and getattr(member, 'phone', None):
            phone_prefix = member.phone[:3] if member.phone else "+967"
            random_suffix = str(random.randint(1000000, 9999999))
            random_phone = f"{phone_prefix}{random_suffix}"
            
            contact = InputPhoneContact(
                client_id=random.randint(0, 10000),
                phone=random_phone,
                first_name=member.first_name or "",
                last_name=member.last_name or ""
            )
            contacts.append(contact)
    
    if contacts:
        try:
            batch_size = 10  # تقليل الحجم لتجنب الأخطاء
            for i in range(0, len(contacts), batch_size):
                batch = contacts[i:i + batch_size]
                result = await client(ImportContactsRequest(batch))
                added.extend(result.users)
                await asyncio.sleep(2)
        except Exception as e:
            print(f"Error adding contacts: {e}")
    
    return added

async def add_to_target(target, contacts, user_id):
    added = []
    process_status = load_process_status()
    
    try:
        entity = await client.get_entity(target)
        
        for i, contact in enumerate(contacts):
            if process_status.get(user_id, {}).get('cancelled', False):
                break
                
            try:
                if hasattr(entity, 'broadcast') and entity.broadcast:
                    await client(InviteToChannelRequest(
                        channel=entity,
                        users=[contact]
                    ))
                else:
                    await client(AddChatUserRequest(
                        chat_id=entity.id,
                        user_id=contact.id,
                        fwd_limit=0
                    ))
                added.append(contact)
                
                if (i + 1) % 5 == 0:  # تقليل التحديثات
                    progress_text = f"""
╔══════════════════════╗
       📈 **التقدم**  
╚══════════════════════╝

✅ *تم إضافة {i + 1} من {len(contacts)} عضو*
⏳ *جاري الاستمرار...*
                    """
                    bot.send_message(user_id, progress_text, parse_mode='Markdown')
                
                await asyncio.sleep(5)  # زيادة وقت الانتظار
                    
            except errors.FloodWaitError as e:
                wait_text = f"""
╔══════════════════════╗
       ⏳ **انتظر**  
╚══════════════════════╝

⏰ *جاري الانتظار {e.seconds} ثانية*
🛡️ *بسبب قيود Telegram*
                """
                bot.send_message(user_id, wait_text, parse_mode='Markdown')
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"Error adding user {contact.id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error adding to target: {e}")
    
    return added

# تشغيل البوت
if __name__ == "__main__":
    print("🤖 Bot is running...")
    
    def run_client():
        try:
            client.start()
            client.run_until_disconnected()
        except Exception as e:
            print(f"Client error: {e}")
    
    client_thread = threading.Thread(target=run_client)
    client_thread.daemon = True
    client_thread.start()
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Bot error: {e}")
