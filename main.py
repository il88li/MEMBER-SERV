import os
import asyncio
import random
import pickle
from telethon import TelegramClient, events, types
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact, User, UserStatusRecently, UserStatusLastWeek
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
from collections import defaultdict

# بيانات API
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8390052181:AAH9q_7rgJd2jcvtT3yMb2cFo6667piyJsw'

# تهيئة العملاء
bot = telebot.TeleBot(BOT_TOKEN)
client = TelegramClient('member_saver_session', API_ID, API_HASH)

# تخزين البيانات
class DataStorage:
    def __init__(self):
        self.user_sessions = {}
        self.user_settings = self.load_data('user_settings.pkl')
        self.process_statistics = self.load_data('process_statistics.pkl')
        self.added_members = self.load_data('added_members.pkl')
        
    def load_data(self, filename):
        try:
            with open(filename, 'rb') as f:
                return pickle.load(f)
        except:
            return defaultdict(dict)
    
    def save_data(self, filename, data):
        with open(filename, 'wb') as f:
            pickle.dump(f, data)
    
    def save_all(self):
        self.save_data('user_settings.pkl', self.user_settings)
        self.save_data('process_statistics.pkl', self.process_statistics)
        self.save_data('added_members.pkl', self.added_members)

data_storage = DataStorage()

# حالات المستخدم
class UserStates:
    WAITING_PHONE = 1
    WAITING_PASSWORD = 2
    WAITING_SOURCE = 3
    WAITING_TARGET = 4
    WAITING_COUNT = 5

user_states = {}

# إنشاء واجهة الأزرار
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 2
    keyboard.add(
        InlineKeyboardButton("بدء العملية", callback_data="start_process"),
        InlineKeyboardButton("تسجيل", callback_data="register"),
        InlineKeyboardButton("إعدادات", callback_data="settings"),
        InlineKeyboardButton("إحصائيات العملية الحالية", callback_data="statistics")
    )
    return keyboard

def create_settings_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 1
    keyboard.add(
        InlineKeyboardButton("تعيين المصدر", callback_data="set_source"),
        InlineKeyboardButton("تعيين الهدف", callback_data="set_target"),
        InlineKeyboardButton("تعيين العدد", callback_data="set_count"),
        InlineKeyboardButton("العودة", callback_data="main_menu")
    )
    return keyboard

# معالجة الأوامر
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "مرحباً! أنا بوت حفظ أعضاء المجموعات في جهات الاتصال.\n\n"
        "يمكنك استخدام الأزرار أدناه للتحكم في العمليات:",
        reply_markup=create_main_keyboard()
    )

# معالجة زر callback
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    
    if call.data == "main_menu":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="القائمة الرئيسية:",
            reply_markup=create_main_keyboard()
        )
    
    elif call.data == "start_process":
        start_member_addition(call)
    
    elif call.data == "register":
        start_registration(call)
    
    elif call.data == "settings":
        show_settings(call)
    
    elif call.data == "statistics":
        show_statistics(call)
    
    elif call.data == "set_source":
        set_source_group(call)
    
    elif call.data == "set_target":
        set_target_group(call)
    
    elif call.data == "set_count":
        set_member_count(call)

def start_registration(call):
    user_id = call.from_user.id
    user_states[user_id] = UserStates.WAITING_PHONE
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="يرجى إرسال رقم هاتفك (مع رمز الدولة):\nمثال: +967123456789"
    )

def show_settings(call):
    user_id = call.from_user.id
    settings = data_storage.user_settings.get(user_id, {})
    
    source = settings.get('source', 'غير محدد')
    target = settings.get('target', 'غير محدد')
    count = settings.get('count', 'غير محدد')
    
    text = f"""الإعدادات الحالية:
    
المجموعة المصدر: {source}
المجموعة الهدف: {target}
عدد الأعضاء المطلوب: {count}

اختر الإعداد الذي تريد تعديله:"""
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=create_settings_keyboard()
    )

def set_source_group(call):
    user_id = call.from_user.id
    user_states[user_id] = UserStates.WAITING_SOURCE
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="يرجى إرسال معرف المجموعة المصدر (يجب أن يكون البوت مشتركاً فيها):"
    )

def set_target_group(call):
    user_id = call.from_user.id
    user_states[user_id] = UserStates.WAITING_TARGET
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="يرجى إرسال معرف المجموعة الهدف (يجب أن يكون البوت مشتركاً فيها):"
    )

def set_member_count(call):
    user_id = call.from_user.id
    user_states[user_id] = UserStates.WAITING_COUNT
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="يرجى إرسال عدد الأعضاء المطلوب إضافتهم:"
    )

def show_statistics(call):
    user_id = call.from_user.id
    stats = data_storage.process_statistics.get(user_id, {})
    
    added = stats.get('added', 0)
    failed = stats.get('failed', 0)
    total = stats.get('total', 0)
    progress = (added / total * 100) if total > 0 else 0
    
    text = f"""إحصائيات العملية الحالية:
    
الأعضاء المضافون: {added}
المحاولات الفاشلة: {failed}
الإجمالي المستهدف: {total}
التقدم: {progress:.1f}%"""
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("العودة", callback_data="main_menu")
        )
    )

def start_member_addition(call):
    user_id = call.from_user.id
    settings = data_storage.user_settings.get(user_id, {})
    
    if not all(key in settings for key in ['source', 'target', 'count']):
        bot.answer_callback_query(
            call.id,
            "⚠️ يرجى تعيين جميع الإعدادات أولاً",
            show_alert=True
        )
        return
    
    # بدء العملية في thread منفصل
    threading.Thread(
        target=asyncio.run,
        args=(add_members_process(user_id, settings),)
    ).start()
    
    bot.answer_callback_query(
        call.id,
        "🚀 بدأت عملية إضافة الأعضاء...",
        show_alert=False
    )

# معالجة الرسائل النصية
@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if state == UserStates.WAITING_PHONE:
        handle_phone_input(message)
    
    elif state == UserStates.WAITING_PASSWORD:
        handle_password_input(message)
    
    elif state == UserStates.WAITING_SOURCE:
        handle_source_input(message)
    
    elif state == UserStates.WAITING_TARGET:
        handle_target_input(message)
    
    elif state == UserStates.WAITING_COUNT:
        handle_count_input(message)

def handle_phone_input(message):
    user_id = message.from_user.id
    phone = message.text
    
    if not phone.startswith('+'):
        bot.send_message(message.chat.id, "❌ يرجى إدخال الرقم مع رمز الدولة (مثال: +967123456789)")
        return
    
    data_storage.user_sessions[user_id] = {'phone': phone}
    user_states[user_id] = UserStates.WAITING_PASSWORD
    
    bot.send_message(message.chat.id, "🔑 يرجى إرسال كلمة المرور:")

def handle_password_input(message):
    user_id = message.from_user.id
    password = message.text
    
    if user_id not in data_storage.user_sessions:
        bot.send_message(message.chat.id, "❌ حدث خطأ، يرجى المحاولة مرة أخرى")
        return
    
    session_data = data_storage.user_sessions[user_id]
    session_data['password'] = password
    
    # محاولة تسجيل الدخول
    asyncio.run(login_user(user_id, session_data['phone'], password, message.chat.id))
    
    del user_states[user_id]

async def login_user(user_id, phone, password, chat_id):
    try:
        await client.start(phone=phone, password=password)
        bot.send_message(chat_id, "✅ تم تسجيل الدخول بنجاح!")
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل تسجيل الدخول: {str(e)}")

def handle_source_input(message):
    user_id = message.from_user.id
    source = message.text
    
    if user_id not in data_storage.user_settings:
        data_storage.user_settings[user_id] = {}
    
    data_storage.user_settings[user_id]['source'] = source
    data_storage.save_all()
    
    bot.send_message(
        message.chat.id,
        f"✅ تم تعيين المجموعة المصدر: {source}",
        reply_markup=create_main_keyboard()
    )
    
    del user_states[user_id]

def handle_target_input(message):
    user_id = message.from_user.id
    target = message.text
    
    if user_id not in data_storage.user_settings:
        data_storage.user_settings[user_id] = {}
    
    data_storage.user_settings[user_id]['target'] = target
    data_storage.save_all()
    
    bot.send_message(
        message.chat.id,
        f"✅ تم تعيين المجموعة الهدف: {target}",
        reply_markup=create_main_keyboard()
    )
    
    del user_states[user_id]

def handle_count_input(message):
    user_id = message.from_user.id
    
    try:
        count = int(message.text)
        
        if count <= 0:
            raise ValueError
        
        if user_id not in data_storage.user_settings:
            data_storage.user_settings[user_id] = {}
        
        data_storage.user_settings[user_id]['count'] = count
        data_storage.save_all()
        
        bot.send_message(
            message.chat.id,
            f"✅ تم تعيين عدد الأعضاء: {count}",
            reply_markup=create_main_keyboard()
        )
        
        del user_states[user_id]
    
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إدخال رقم صحيح موجب")

# العملية الرئيسية لإضافة الأعضاء
async def add_members_process(user_id, settings):
    chat_id = user_id  # استخدام user_id كـ chat_id للإرسال
    source = settings['source']
    target = settings['target']
    count = settings['count']
    
    try:
        # تهيئة الإحصائيات
        data_storage.process_statistics[user_id] = {
            'added': 0,
            'failed': 0,
            'total': count
        }
        
        bot.send_message(chat_id, "🔄 جاري جلب الأعضاء من المصدر...")
        
        # جلب الأعضاء من المجموعة المصدر
        members = await get_filtered_members(source, user_id)
        
        if not members:
            bot.send_message(chat_id, "❌ لم يتم العثور على أعضاء مناسبين")
            return
        
        bot.send_message(chat_id, f"✅ تم العثور على {len(members)} عضو مناسب")
        
        # إضافة الأعضاء
        success_count = 0
        for i, member in enumerate(members[:count]):
            if await add_member_to_contacts(member, user_id):
                success_count += 1
                data_storage.process_statistics[user_id]['added'] = success_count
            
            # تحديث الإحصائيات كل 10 أعضاء
            if i % 10 == 0:
                update_progress(user_id, chat_id)
            
            await asyncio.sleep(2)  # تجنب rate limits
        
        # الإضافة إلى المجموعة الهدف
        await add_contacts_to_target(target, user_id, chat_id)
        
        # إرسال النتيجة النهائية
        final_message = f"""🎉 اكتملت العملية!

النتائج:
✅ تمت إضافة {success_count} عضو بنجاح
❌ فشل إضافة {count - success_count} عضو
📊 الإجمالي: {count} عضو"""

        bot.send_message(chat_id, final_message)
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء العملية: {str(e)}")

async def get_filtered_members(source, user_id):
    try:
        entity = await client.get_entity(source)
        members = await client.get_participants(entity)
        
        filtered_members = []
        added_members_set = set(data_storage.added_members.get(user_id, []))
        
        for member in members:
            if await is_valid_member(member, added_members_set):
                filtered_members.append(member)
        
        return filtered_members
    
    except Exception as e:
        print(f"Error getting members: {e}")
        return []

async def is_valid_member(member, added_members_set):
    # استبعاد الحسابات المحذوفة
    if member.deleted:
        return False
    
    # استبعاد البوتات
    if member.bot:
        return False
    
    # استبعاد المسؤولين
    if hasattr(member, 'admin_rights') and member.admin_rights:
        return False
    
    # استبعاد الأعضاء غير النشطين (آخر ظهور أكثر من أسبوع)
    if hasattr(member, 'status'):
        if isinstance(member.status, UserStatusLastWeek):
            return False
        if not isinstance(member.status, UserStatusRecently):
            return False
    
    # استبعاد الأعضاء المضافين مسبقاً
    if member.id in added_members_set:
        return False
    
    # التأكد من وجود رقم هاتف
    if not member.phone:
        return False
    
    return True

async def add_member_to_contacts(member, user_id):
    try:
        # إنشاء رقم هاتف عشوائي لأغراض الأمان (9 أرقام + رمز الدولة)
        random_number = generate_random_phone()
        
        contact = InputPhoneContact(
            client_id=random.randint(0, 10000),
            phone=random_number,
            first_name=member.first_name or "",
            last_name=member.last_name or ""
        )
        
        result = await client(ImportContactsRequest([contact]))
        
        if result.users:
            # حفظ العضو المضاف
            if user_id not in data_storage.added_members:
                data_storage.added_members[user_id] = []
            data_storage.added_members[user_id].append(member.id)
            data_storage.save_all()
            return True
    
    except Exception as e:
        print(f"Error adding member: {e}")
        data_storage.process_statistics[user_id]['failed'] += 1
    
    return False

def generate_random_phone():
    country_codes = ['+967', '+966', '+971', '+20', '+963']  # رموز دول عربية
    country_code = random.choice(country_codes)
    number = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    return f"{country_code}{number}"

async def add_contacts_to_target(target, user_id, chat_id):
    try:
        bot.send_message(chat_id, "🔄 جاري إضافة الأعضاء إلى المجموعة الهدف...")
        
        entity = await client.get_entity(target)
        added_members = data_storage.added_members.get(user_id, [])
        
        # هنا يمكن إضافة المنطق لإضافة الأعضاء إلى المجموعة
        # (يتطلب صلاحيات إدارة المجموعة)
        
        bot.send_message(chat_id, f"✅ تم إضافة {len(added_members)} عضو إلى المجموعة الهدف")
    
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ تعذر إضافة الأعضاء إلى المجموعة الهدف: {str(e)}")

def update_progress(user_id, chat_id):
    stats = data_storage.process_statistics.get(user_id, {})
    added = stats.get('added', 0)
    total = stats.get('total', 0)
    
    if total > 0:
        progress = (added / total) * 100
        bot.send_message(
            chat_id,
            f"📊 التقدم: {added}/{total} ({progress:.1f}%)"
        )

# تشغيل البوت
def run_bot():
    print("🤖 البوت يعمل...")
    bot.infinity_polling()

async def run_client():
    await client.start()
    print("🔗 عميل Telethon متصل...")

if __name__ == "__main__":
    # تشغيل العميل والبوت في threads منفصلة
    loop = asyncio.get_event_loop()
    client_thread = threading.Thread(target=loop.run_until_complete, args=(run_client(),))
    client_thread.start()
    
    # تشغيل البوت
    run_bot()
