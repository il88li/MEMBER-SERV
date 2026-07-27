# bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.config import DEVELOPER_LINK, PROMO_CHANNEL_ID

# ثوابت الأزرار
BTN_EXTRACT = "استخراج برومبت"
BTN_POINTS = "تجميع نقاط"
BTN_DEVELOPER = "DEVELOPER"
BTN_PROMO = "📢 أحدث البرومبتات"
BTN_BACK = "↩️ رجوع"
BTN_VERIFY = "✅ تحقق"
BTN_CONTACT_DEV = "📩 تواصل مع المطور"

def main_menu_keyboard():
    """لوحة القائمة الرئيسية."""
    keyboard = [
        [InlineKeyboardButton(BTN_EXTRACT, callback_data="extract")],
        [InlineKeyboardButton(BTN_POINTS, callback_data="points"),
         InlineKeyboardButton(BTN_DEVELOPER, callback_data="developer")],
        [InlineKeyboardButton(BTN_PROMO, url=f"https://t.me/{PROMO_CHANNEL_ID.lstrip('@')}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def points_menu_keyboard():
    """لوحة قائمة النقاط (تحتوي على زر رجوع)."""
    keyboard = [
        [InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def subscription_check_keyboard():
    """لوحة التحقق من الاشتراك."""
    keyboard = [
        [InlineKeyboardButton(BTN_VERIFY, callback_data="check_sub")]
    ]
    return InlineKeyboardMarkup(keyboard)

def developer_keyboard():
    """لوحة زر التواصل مع المطور."""
    keyboard = [
        [InlineKeyboardButton(BTN_CONTACT_DEV, url=DEVELOPER_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    """لوحة زر رجوع بسيطة."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]
    ])

def cancel_keyboard():
    """لوحة زر إلغاء."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_extract")]
    ])