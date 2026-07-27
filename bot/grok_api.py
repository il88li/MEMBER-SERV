# bot/grok_api.py
import cloudscraper
import json
import re
import time
import tempfile
import os
import requests
import logging

logger = logging.getLogger(__name__)

_grok_token = None
_grok_chat_uuid = None
_grok_email = None
_grok_email_id = None
_grok_session_expiry = 0
GROK_SESSION_TIMEOUT = 3600

ZECO_URL = "https://zecora0.serv00.net/Gmail.php"

def _create_email():
    scraper = cloudscraper.create_scraper()
    try:
        resp = scraper.get(f"{ZECO_URL}?action=create", timeout=15)
        if resp.status_code != 200:
            raise Exception(f"فشل إنشاء البريد (HTTP {resp.status_code})")
        data = resp.json()
        if 'error' in data or not data.get('email'):
            raise Exception(f"فشل إنشاء البريد: {data}")
        return data['email'], data['id']
    except Exception as e:
        raise Exception(f"خطأ في إنشاء البريد: {e}")

def _send_otp(email, scraper):
    resp = scraper.post(
        'https://api.syntx.ai/api/v1/auth/email/send-otp',
        json={"email": email, "ref_uuid": None, "utm": ""},
        headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'},
        timeout=30
    )
    if resp.status_code != 200 or not resp.json().get('success'):
        raise Exception(f"فشل إرسال رمز التحقق (HTTP {resp.status_code})")
    logger.info("تم إرسال OTP بنجاح")

def _wait_for_otp(email, email_id, scraper, timeout=180):
    last_id = None
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = scraper.get(
                f"{ZECO_URL}?action=get_messages&mailbox_id={email_id}&email={email}",
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0 and data[0].get('id') != last_id:
                    last_id = data[0]['id']
                    content = data[0].get('html', '') or data[0].get('text', '') or data[0].get('body', '')
                    match = re.search(r'\b(\d{6})\b', content)
                    if match:
                        logger.info("تم استلام OTP")
                        return match.group(1)
        except Exception as e:
            logger.debug(f"خطأ في انتظار OTP: {e}")
        time.sleep(2)
    raise Exception("لم يتم استلام رمز التحقق خلال المهلة")

def _verify_otp(email, otp, scraper):
    resp = scraper.post(
        'https://api.syntx.ai/api/v1/auth/email/verify-otp',
        json={"email": email, "otp_code": otp, "ref_uuid": None, "utm": ""},
        headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'},
        timeout=30
    )
    if resp.status_code != 200 or not resp.json().get('success'):
        raise Exception(f"فشل التحقق من الرمز (HTTP {resp.status_code})")
    token = resp.json().get('token')
    if not token:
        raise Exception("لم يتم استلام توكن")
    logger.info("تم التحقق من OTP واستلام التوكن")
    return token

def _create_chat(token, scraper):
    resp = scraper.post(
        'https://api.syntx.ai/api/v1/chats',
        json={"title": "Grok Chat", "scope": "text"},
        headers={'Authorization': f'Bearer {token}', 'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'},
        timeout=30
    )
    if resp.status_code != 201:
        raise Exception(f"فشل إنشاء المحادثة (HTTP {resp.status_code})")
    uuid = resp.json().get('uuid')
    if not uuid:
        raise Exception("لم يتم استلام UUID")
    logger.info(f"تم إنشاء المحادثة: {uuid}")
    return uuid

def init_grok_session(max_retries=3):
    global _grok_token, _grok_chat_uuid, _grok_email, _grok_email_id
    for attempt in range(max_retries):
        try:
            scraper = cloudscraper.create_scraper()
            _grok_email, _grok_email_id = _create_email()
            _send_otp(_grok_email, scraper)
            otp = _wait_for_otp(_grok_email, _grok_email_id, scraper, timeout=180)
            _grok_token = _verify_otp(_grok_email, otp, scraper)
            _grok_chat_uuid = _create_chat(_grok_token, scraper)
            logger.info(f"تم تهيئة جلسة Grok بنجاح (المحاولة {attempt+1})")
            return _grok_token, _grok_chat_uuid
        except Exception as e:
            logger.error(f"محاولة {attempt+1}/{max_retries} فشلت في تهيئة جلسة Grok: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
    return _grok_token, _grok_chat_uuid

def get_grok_session():
    global _grok_token, _grok_chat_uuid, _grok_session_expiry
    now = time.time()
    if not _grok_token or not _grok_chat_uuid or (now + 300) > _grok_session_expiry:
        logger.info("جلسة Grok منتهية أو على وشك الانتهاء، إعادة التهيئة...")
        token, uuid = init_grok_session()
        if token and uuid:
            _grok_token = token
            _grok_chat_uuid = uuid
            _grok_session_expiry = now + GROK_SESSION_TIMEOUT
            return _grok_token, _grok_chat_uuid
        raise Exception("تعذر تهيئة جلسة Grok")
    return _grok_token, _grok_chat_uuid

def force_refresh_session():
    global _grok_token, _grok_chat_uuid, _grok_session_expiry
    logger.info("إعادة تهيئة جلسة Grok (فرض)...")
    _grok_token = None
    _grok_chat_uuid = None
    _grok_session_expiry = 0
    return get_grok_session()

def upload_image_to_grok(chat_uuid, image_bytes, token):
    for attempt in range(2):
        try:
            scraper = cloudscraper.create_scraper()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            try:
                with open(tmp_path, 'rb') as f:
                    files = {'files': (os.path.basename(tmp_path), f, 'application/octet-stream')}
                    data = {'check_duplicates': 'true', 'chat_uuid': chat_uuid}
                    headers = {'Authorization': f'Bearer {token}'}
                    resp = requests.post(
                        'https://api.syntx.ai/api/v1/chats/upload-files',
                        data=data,
                        files=files,
                        headers=headers,
                        timeout=45
                    )
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get('successful', 0) > 0 and result.get('files'):
                        url = result['files'][0]['url']
                        logger.info(f"تم رفع الصورة بنجاح: {url}")
                        return url
                    else:
                        raise Exception("رفع الصورة فشل: response لا يحتوي على ملفات")
                else:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"محاولة رفع الصورة {attempt+1}/2 فشلت: {e}")
            if attempt == 1:
                raise
            time.sleep(2)
    raise Exception("فشل رفع الصورة بعد محاولتين")

def send_message_to_grok(chat_uuid, objects, token):
    for attempt in range(2):
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.post(
                f"https://api.syntx.ai/api/v1/chats/{chat_uuid}/messages?ai_name=grok",
                json={"objects": objects},
                headers={'Authorization': f'Bearer {token}', 'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'},
                timeout=45
            )
            if resp.status_code == 200:
                msg_id = resp.json().get('id')
                if not msg_id:
                    raise Exception("لم يتم استلام معرف الرسالة")
                logger.info(f"تم إرسال الرسالة إلى Grok، المعرف: {msg_id}")
                return msg_id
            else:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"محاولة إرسال الرسالة {attempt+1}/2 فشلت: {e}")
            if attempt == 1:
                raise
            time.sleep(2)
    raise Exception("فشل إرسال الرسالة بعد محاولتين")

def wait_for_reply(chat_uuid, last_msg_id, token, timeout=180):
    scraper = cloudscraper.create_scraper()
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = scraper.get(
                f"https://api.syntx.ai/api/v1/chats/{chat_uuid}/messages?page_size=20",
                headers={'Authorization': f'Bearer {token}', 'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'},
                timeout=20
            )
            if resp.status_code == 200:
                for msg in resp.json().get('messages', []):
                    if msg.get('author_id') == -1 and msg.get('id', 0) > last_msg_id:
                        obj = msg.get('message_object', [{}])[0]
                        if obj and obj.get('object_type') == 'text' and obj.get('completed'):
                            logger.info("تم استلام الرد من Grok")
                            return obj.get('object_text')
            else:
                logger.debug(f"wait_for_reply: HTTP {resp.status_code}")
        except Exception as e:
            logger.debug(f"wait_for_reply: {e}")
        time.sleep(3)
    raise Exception("لم يتم استلام رد من Grok خلال المهلة المحددة")