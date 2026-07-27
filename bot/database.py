import json
import secrets
import requests
import logging
from bot import config

logger = logging.getLogger(__name__)

SUPABASE_URL = config.SUPABASE_URL
SUPABASE_KEY = config.SUPABASE_KEY
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def _supabase_request(method, table, params=None, data=None):
    """إرسال طلب إلى Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        # تحويل params إلى استعلام URL
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{url}?{query}"
    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=HEADERS, timeout=10)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=HEADERS, json=data, timeout=10)
        elif method.upper() == "PATCH":
            resp = requests.patch(url, headers=HEADERS, json=data, timeout=10)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, headers=HEADERS, timeout=10)
        else:
            return None
        if resp.status_code in (200, 201, 204):
            if resp.text:
                return resp.json()
            return True
        logger.error(f"Supabase error {resp.status_code}: {resp.text}")
        return None
    except Exception as e:
        logger.error(f"Supabase request failed: {e}")
        return None

def init_db():
    """إنشاء الجداول (يتم تنفيذها يدوياً مرة واحدة)."""
    # هذه الدالة لا تفعل شيئاً لأننا سننشئ الجداول يدوياً
    logger.info("✅ تأكد من إنشاء الجداول يدوياً في Supabase.")
    return True

def db_get_user(user_id):
    """استرجاع مستخدم."""
    res = _supabase_request("GET", "users", params={"user_id": f"eq.{user_id}"})
    if res and len(res) > 0:
        return res[0]
    return None

def db_add_user(user_id, invited_by=None):
    """إضافة مستخدم جديد."""
    existing = db_get_user(user_id)
    if existing:
        return False
    data = {"user_id": user_id, "points": 1}
    if invited_by and invited_by != user_id:
        data["invited_by"] = invited_by
    res = _supabase_request("POST", "users", data=data)
    if not res:
        return False
    # زيادة نقاط الداعي
    if invited_by and invited_by != user_id:
        db_add_points(invited_by, 1)
        db_add_points(invited_by, 0, invite=True)  # زيادة عدد المدعوين
    return True

def db_add_points(user_id, amount, invite=False):
    """إضافة نقاط لمستخدم."""
    # نحتاج إلى قراءة القيمة الحالية وتحديثها
    user = db_get_user(user_id)
    if not user:
        return False
    new_points = user.get("points", 0) + amount
    data = {"points": new_points}
    if invite:
        data["invite_count"] = user.get("invite_count", 0) + 1
    res = _supabase_request("PATCH", "users", params={"user_id": f"eq.{user_id}"}, data=data)
    return res is not None

def db_is_banned(user_id):
    """التحقق من الحظر."""
    res = _supabase_request("GET", "banned_users", params={"user_id": f"eq.{user_id}"})
    return res is not None and len(res) > 0

def db_ban_user(user_id):
    """حظر مستخدم."""
    data = {"user_id": user_id}
    res = _supabase_request("POST", "banned_users", data=data)
    return res is not None

def db_unban_user(user_id):
    """فك حظر مستخدم."""
    res = _supabase_request("DELETE", "banned_users", params={"user_id": f"eq.{user_id}"})
    return res is not None

def db_get_banned_list():
    """الحصول على قائمة المحظورين."""
    res = _supabase_request("GET", "banned_users", params={"order": "banned_at.desc"})
    return res if res else []

def db_create_gift(points, max_uses):
    """إنشاء رابط هدية."""
    code = secrets.token_hex(6)
    data = {"code": code, "points": points, "max_uses": max_uses}
    res = _supabase_request("POST", "gift_links", data=data)
    if res:
        return code
    return None

def db_get_gift(code):
    """استرجاع معلومات الهدية."""
    res = _supabase_request("GET", "gift_links", params={"code": f"eq.{code}"})
    if res and len(res) > 0:
        return res[0]
    return None

def db_use_gift(code):
    """استخدام هدية (زيادة عدد المستخدمين)."""
    gift = db_get_gift(code)
    if not gift:
        return None
    if gift.get("used_count", 0) >= gift.get("max_uses", 0):
        return "expired"
    new_count = gift.get("used_count", 0) + 1
    data = {"used_count": new_count}
    res = _supabase_request("PATCH", "gift_links", params={"code": f"eq.{code}"}, data=data)
    if res is not None:
        return "success"
    return None

def get_invite_link(user_id):
    return f"https://t.me/{config.BOT_USERNAME}?start=ref_{user_id}"
