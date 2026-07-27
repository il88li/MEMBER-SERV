# bot/keyboards.py
# [+] تعريفات الأزرار - معاد تصميمها لتطبيق نمط 1-2-1

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot import config

# ============================================================
# [+] النصوص الثابتة للأزرار (بدون إيموجي)
# ============================================================

# [+] أزرار القائمة الرئيسية
BTN_EXTRACT: str = "استخراج برومبت"
BTN_POINTS: str = "نظام النقاط"
BTN_INVITE: str = "دعوة الأصدقاء"
BTN_DEVELOPER: str = "المطور"
BTN_PROMO: str = "أحدث البرومبتات"

# [+] أزرار التنقل
BTN_BACK: str = "رجوع"
BTN_VERIFY: str = "تحقق من الاشتراك"
BTN_CONTACT_DEV: str = "تواصل مع المطور"
BTN_CANCEL: str = "إلغاء العملية"
BTN_HOME: str = "القائمة الرئيسية"

# ============================================================
# [+] دوال إنشاء لوحات المفاتيح - نمط 1-2-1
# ============================================================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """[+] لوحة القائمة الرئيسية - نمط 1-2-1"""
    keyboard: list = [
        # [+] الصف الأول: الإجراء الرئيسي (زر واحد)
        [InlineKeyboardButton(BTN_EXTRACT, callback_data="extract")],
        # [+] الصف الثاني: إجراءان ثانويان (زران)
        [
            InlineKeyboardButton(BTN_POINTS, callback_data="points"),
            InlineKeyboardButton(BTN_INVITE, callback_data="invite")
        ],
        # [+] الصف الثالث: إجراء إضافي (زر واحد)
        [InlineKeyboardButton(BTN_DEVELOPER, callback_data="developer")]
    ]
    return InlineKeyboardMarkup(keyboard)

def points_menu_keyboard() -> InlineKeyboardMarkup:
    """[+] لوحة النقاط - زر رجوع فقط"""
    keyboard: list = [
        [InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def subscription_check_keyboard() -> InlineKeyboardMarkup:
    """[+] لوحة التحقق من الاشتراك - نمط 1-1"""
    keyboard: list = [
        [InlineKeyboardButton(BTN_VERIFY, callback_data="check_sub")],
        [InlineKeyboardButton(BTN_HOME, callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def developer_keyboard() -> InlineKeyboardMarkup:
    """[+] لوحة المطور - زر تواصل"""
    keyboard: list = [
        [InlineKeyboardButton(BTN_CONTACT_DEV, url=config.DEVELOPER_LINK)],
        [InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard() -> InlineKeyboardMarkup:
    """[+] زر رجوع فقط"""
    keyboard: list = [
        [InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def cancel_keyboard() -> InlineKeyboardMarkup:
    """[+] زر إلغاء فقط"""
    keyboard: list = [
        [InlineKeyboardButton(BTN_CANCEL, callback_data="cancel_extract")]
    ]
    return InlineKeyboardMarkup(keyboard)

def invite_keyboard() -> InlineKeyboardMarkup:
    """[+] لوحة الدعوة - زر رجوع"""
    keyboard: list = [
        [InlineKeyboardButton(BTN_BACK, callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)