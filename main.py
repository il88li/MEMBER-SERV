import telebot
from telebot import types
from google import genai
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import datetime

# تهيئة البوت و Gemini
BOT_TOKEN = "8228285723:AAGLH7ljG2lyMQ6SaMVZVqf-Y44zVdMLDRo"
GEMINI_API_KEY = "AIzaSyABlAHgp2wpiH3OKzOHq2QKiI2xjIQaPAE"
CHANNEL_USERNAME = "@iIl337"

client = genai.Client(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(BOT_TOKEN)

# تخزين البيانات
user_channels = {}
user_generated_content = {}

# وظيفة توليد المحتوى
def generate_black_comedy_content():
    prompt = "اكتب عبارة نصية مكونة من سطر واحد كوميدية سوداء يائسة فيها نمط كبريائي نرجسي في سطر واحد فقط لا غير بحد أقصى 50 حرفا للعبارة"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        content = response.text.strip()
        # إضافة اسم البوت في الأسفل بخط عريض
        final_content = f"{content}\n\n**@TeSi7_BOT**"
        return final_content
    except Exception as e:
        return "عذرًا، حدث خطأ في توليد المحتوى.\n\n**@TeSi7_BOT**"

# جدولة النشر التلقائي
def schedule_posts():
    scheduler = BackgroundScheduler()
    
    # 6 صباحًا، 12 مساءً، 9 مساءً
    times = [(6, 0), (12, 0), (21, 0)]
    
    for hour, minute in times:
        scheduler.add_job(
            auto_post_content,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=f"post_{hour}_{minute}"
        )
    
    scheduler.start()

def auto_post_content():
    content = generate_black_comedy_content()
    
    for user_id, channels in user_channels.items():
        for channel in channels:
            try:
                bot.send_message(channel, content, parse_mode='Markdown')
            except Exception as e:
                print(f"خطأ في النشر إلى {channel}: {e}")

# لوحة المفاتيح الرئيسية
def main_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("إدارة القنوات", callback_data="manage_channels")
    btn2 = types.InlineKeyboardButton("الإعدادات ⚙️", callback_data="settings")
    keyboard.add(btn1, btn2)
    return keyboard

# لوحة إدارة القنوات
def channels_keyboard(user_id):
    keyboard = types.InlineKeyboardMarkup()
    
    if user_id in user_channels and user_channels[user_id]:
        for i, channel in enumerate(user_channels[user_id], 1):
            keyboard.add(types.InlineKeyboardButton(
                f"القناة {i} - {channel}", 
                callback_data=f"view_channel_{i}"
            ))
    
    if user_id not in user_channels or len(user_channels[user_id]) < 3:
        keyboard.add(types.InlineKeyboardButton(
            "➕ إضافة قناة", 
            callback_data="add_channel"
        ))
    
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    return keyboard

# لوحة الإعدادات الرئيسية
def settings_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("توليد الآن 🚀", callback_data="generate_now"))
    keyboard.add(types.InlineKeyboardButton("عن البوت ℹ️", callback_data="about_bot"))
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    return keyboard

# لوحة بعد التوليد
def after_generation_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("نشر الآن 📤", callback_data="publish_now"),
        types.InlineKeyboardButton("توليد آخر 🔄", callback_data="generate_another")
    )
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_settings"))
    return keyboard

# التحقق من الاشتراك
def check_subscription(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.reply_to(message, f"⚠️ يجب الاشتراك في القناة أولاً:\n{CHANNEL_USERNAME}")
        return
    
    welcome_text = "مرحباً! أنا بوت توليد المحتوى التلقائي 🚀\n\nاختر من الخيارات أدناه:"
    bot.send_message(user_id, welcome_text, reply_markup=main_keyboard())

# معالجة الأزرار
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if not check_subscription(user_id):
        bot.answer_callback_query(call.id, "⚠️ يجب الاشتراك في القناة أولاً")
        return
    
    if call.data == "manage_channels":
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="🛠️ إدارة قنواتك:",
            reply_markup=channels_keyboard(user_id)
        )
    
    elif call.data == "settings":
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="⚙️ الإعدادات:",
            reply_markup=settings_keyboard()
        )
    
    elif call.data == "generate_now":
        # توليد المحتوى وعرضه مع الأزرار الجديدة
        content = generate_black_comedy_content()
        user_generated_content[user_id] = content
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=f"📝 المحتوى المُولد:\n\n{content}\n\nماذا تريد أن تفعل؟",
            parse_mode='Markdown',
            reply_markup=after_generation_keyboard()
        )
    
    elif call.data == "publish_now":
        if user_id not in user_channels or not user_channels[user_id]:
            bot.answer_callback_query(call.id, "❌ لا توجد قنوات مضافة للنشر")
            return
        
        content = user_generated_content.get(user_id, generate_black_comedy_content())
        success_count = 0
        
        for channel in user_channels[user_id]:
            try:
                bot.send_message(channel, content, parse_mode='Markdown')
                success_count += 1
            except Exception as e:
                print(f"خطأ في النشر: {e}")
        
        bot.answer_callback_query(call.id, f"✅ تم النشر في {success_count} قناة")
    
    elif call.data == "generate_another":
        # توليد محتوى جديد
        content = generate_black_comedy_content()
        user_generated_content[user_id] = content
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=f"📝 المحتوى المُولد:\n\n{content}\n\nماذا تريد أن تفعل؟",
            parse_mode='Markdown',
            reply_markup=after_generation_keyboard()
        )
    
    elif call.data == "about_bot":
        about_text = """🤖 **عن البوت**
        
بوت ذكي لتوليد محتوى كوميدي تلقائي باستخدام الذكاء الاصطناعي!

**المميزات:**
• توليد محتوى كوميدي سوداء تلقائي
• نشر تلقائي في الأوقات المحددة
• دعم متعدد القنوات
• واجهة سهلة الاستخدام

**المطور:** @iIl337
**البوت:** @TeSi7_BOT"""
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=about_text,
            parse_mode='Markdown',
            reply_markup=settings_keyboard()
        )
    
    elif call.data == "add_channel":
        if user_id in user_channels and len(user_channels[user_id]) >= 3:
            bot.answer_callback_query(call.id, "❌ وصلت للحد الأقصى (3 قنوات)")
            return
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="🔗 أرسل معرف القناة الآن (مثال: @channel_name)"
        )
        bot.register_next_step_handler(call.message, process_channel_add)
    
    elif call.data.startswith("view_channel_"):
        channel_index = int(call.data.split("_")[2]) - 1
        if user_id in user_channels and 0 <= channel_index < len(user_channels[user_id]):
            channel = user_channels[user_id][channel_index]
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("🗑️ حذف القناة", callback_data=f"delete_confirm_{channel_index}"))
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="manage_channels"))
            
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=f"📋 معلومات القناة:\n\n{channel}",
                reply_markup=keyboard
            )
    
    elif call.data.startswith("delete_confirm_"):
        channel_index = int(call.data.split("_")[2])
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("✅ نعم، احذف", callback_data=f"delete_{channel_index}"))
        keyboard.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="manage_channels"))
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="⚠️ هل أنت متأكد من حذف هذه القناة؟",
            reply_markup=keyboard
        )
    
    elif call.data.startswith("delete_"):
        channel_index = int(call.data.split("_")[1])
        if user_id in user_channels and 0 <= channel_index < len(user_channels[user_id]):
            deleted_channel = user_channels[user_id].pop(channel_index)
            bot.answer_callback_query(call.id, f"✅ تم حذف {deleted_channel}")
            
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text="🛠️ إدارة قنواتك:",
                reply_markup=channels_keyboard(user_id)
            )
    
    elif call.data == "back_main":
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="مرحباً! أنا بوت توليد المحتوى التلقائي 🚀\n\nاختر من الخيارات أدناه:",
            reply_markup=main_keyboard()
        )
    
    elif call.data == "back_settings":
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="⚙️ الإعدادات:",
            reply_markup=settings_keyboard()
        )

def process_channel_add(message):
    user_id = message.from_user.id
    channel = message.text.strip()
    
    if user_id not in user_channels:
        user_channels[user_id] = []
    
    if len(user_channels[user_id]) >= 3:
        bot.send_message(user_id, "❌ وصلت للحد الأقصى (3 قنوات)")
        return
    
    if channel.startswith('@'):
        user_channels[user_id].append(channel)
        bot.send_message(
            user_id, 
            f"✅ تم إضافة {channel} بنجاح", 
            reply_markup=channels_keyboard(user_id)
        )
    else:
        bot.send_message(user_id, "❌ يجب أن يبدأ معرف القناة ب @")

# بدء الجدولة عند التشغيل
if __name__ == "__main__":
    print("🤖 البوت يعمل...")
    schedule_posts()
    bot.polling(none_stop=True)
