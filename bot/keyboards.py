# bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot import config

BTN_EXTRACT = "استخراج برومبت"
BTN_POINTS = "تجميع نقاط"
BTN_DEVELOPER = "DEVELOPER"
BTN_PROMO = "📢 أحدث البرومبتات"
BTN_BACK = "↩️ رجوع"
BTN_VERIFY = "✅ تحقق"
BTN_CONTACT_DEV = "📩 تواصل مع المطور"

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(BTN_EXTRACT, callback_data="extract")],
        [InlineKeyboardButton(BTN_POINTS, callback_data="points"), InlineKeyboardButton(BTN_DEVELOPER, callback_data="developer")],
        [InlineKeyboardButton(BTN_PROMO, url=f"https://t.me/{config.PROMO_CHANNEL_ID.lstrip('@')}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def points_menu_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]])

def subscription_check_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_VERIFY, callback_data="check_sub")]])

def developer_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_CONTACT_DEV, url=config.DEVELOPER_LINK)]])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]])

def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_extract")]])