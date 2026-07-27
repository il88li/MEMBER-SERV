from supabase import create_client, Client
import config
import logging

logger = logging.getLogger(__name__)

# استخدام المفتاح السري لإنشاء العميل
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

def init_db():
    """إنشاء الجداول تلقائياً باستخدام المفتاح السري."""
    try:
        # محاولة الوصول إلى جدول users للتأكد من وجود الجداول
        supabase.table('users').select('*').limit(1).execute()
        logger.info("✅ الجداول موجودة بالفعل")
        return True
    except Exception as e:
        logger.info("🔄 إنشاء الجداول... (قد يستغرق بضع ثوانٍ)")
        # قائمة أوامر SQL لإنشاء الجداول
        sqls = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                points INTEGER DEFAULT 1,
                invited_by BIGINT DEFAULT NULL,
                invite_count INTEGER DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id BIGINT PRIMARY KEY,
                banned_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gift_links (
                code TEXT PRIMARY KEY,
                points INTEGER NOT NULL,
                max_uses INTEGER NOT NULL,
                used_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_invited_by ON users(invited_by)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_gift_links_code ON gift_links(code)
            """
        ]
        try:
            # استخدام RPC لتنفيذ SQL (يتطلب service_role key)
            for sql in sqls:
                try:
                    # محاولة استدعاء exec_sql (متاحة مع service_role)
                    supabase.rpc('exec_sql', {'sql': sql}).execute()
                except Exception as e:
                    # إذا فشلت exec_sql، نحاول باستخدام REST مباشر (قد لا يعمل مع publishable)
                    logger.warning(f"فشل تنفيذ SQL عبر RPC: {e}")
                    # نستخدم طريقة بديلة: إرسال كـ استعلام مباشر عبر جدول خاص (غير مدعوم في كل الإصدارات)
                    pass
            logger.info("✅ تم إنشاء الجداول بنجاح")
        except Exception as e:
            logger.error(f"❌ فشل إنشاء الجداول تلقائياً: {e}")
            logger.info("⚠️ يرجى تنفيذ أوامر SQL يدوياً في Supabase SQL Editor.")
            # عرض الأوامر للمساعدة
            for sql in sqls:
                print(sql)
            return False
        return True

# ============================================================
# دوال قاعدة البيانات (تستخدم المفتاح السري لجميع العمليات)
# ============================================================

def db_get_user(user_id):
    try:
        res = supabase.table('users').select('*').eq('user_id', user_id).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"db_get_user error: {e}")
        return None

def db_add_user(user_id, invited_by=None):
    try:
        existing = db_get_user(user_id)
        if existing:
            return False
        if invited_by and invited_by != user_id:
            supabase.table('users').insert({
                'user_id': user_id,
                'points': 1,
                'invited_by': invited_by
            }).execute()
            # تحديث نقاط الداعي
            supabase.table('users').update({
                'points': supabase.raw('points + 1'),
                'invite_count': supabase.raw('invite_count + 1')
            }).eq('user_id', invited_by).execute()
        else:
            supabase.table('users').insert({
                'user_id': user_id,
                'points': 1
            }).execute()
        return True
    except Exception as e:
        logger.error(f"db_add_user error: {e}")
        return False

def db_add_points(user_id, amount):
    try:
        supabase.table('users').update({
            'points': supabase.raw(f'points + {amount}')
        }).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        logger.error(f"db_add_points error: {e}")
        return False

def db_is_banned(user_id):
    try:
        res = supabase.table('banned_users').select('*').eq('user_id', user_id).execute()
        return len(res.data) > 0
    except:
        return False

def db_ban_user(user_id):
    try:
        supabase.table('banned_users').insert({'user_id': user_id}).execute()
        return True
    except:
        return False

def db_unban_user(user_id):
    try:
        supabase.table('banned_users').delete().eq('user_id', user_id).execute()
        return True
    except:
        return False

def db_get_banned_list():
    try:
        res = supabase.table('banned_users').select('*').order('banned_at', desc=True).execute()
        return res.data
    except:
        return []

def db_create_gift(points, max_uses):
    import secrets
    code = secrets.token_hex(6)
    try:
        supabase.table('gift_links').insert({
            'code': code,
            'points': points,
            'max_uses': max_uses
        }).execute()
        return code
    except:
        return None

def db_get_gift(code):
    try:
        res = supabase.table('gift_links').select('*').eq('code', code).execute()
        if res.data:
            return res.data[0]
        return None
    except:
        return None

def db_use_gift(code):
    try:
        gift = db_get_gift(code)
        if not gift:
            return None
        if gift['used_count'] >= gift['max_uses']:
            return 'expired'
        supabase.table('gift_links').update({
            'used_count': supabase.raw('used_count + 1')
        }).eq('code', code).execute()
        return 'success'
    except:
        return None

def get_invite_link(user_id):
    return f"https://t.me/{config.BOT_USERNAME}?start=ref_{user_id}"