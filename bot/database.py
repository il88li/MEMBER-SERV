from supabase import create_client, Client
import config

# استخدام القيم المضمنة مباشرة من config
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

def init_db():
    """تهيئة قاعدة البيانات (يتم إنشاء الجداول يدوياً في Supabase)."""
    pass

def db_get_user(user_id):
    try:
        res = supabase.table('users').select('*').eq('user_id', user_id).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
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
        return False

def db_add_points(user_id, amount):
    try:
        supabase.table('users').update({
            'points': supabase.raw(f'points + {amount}')
        }).eq('user_id', user_id).execute()
        return True
    except Exception as e:
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