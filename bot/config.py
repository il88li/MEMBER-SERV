# bot/config.py
# [+] ملف الإعدادات - تم نقل الأسرار إلى متغيرات البيئة

import os
from typing import Optional

# ============================================================
# [+] قراءة الإعدادات من متغيرات البيئة
# ============================================================

def get_env(key: str, default: Optional[str] = None) -> str:
    """[+] الحصول على قيمة من متغيرات البيئة مع قيمة افتراضية"""
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"[-] المتغير البيئي {key} غير مُعيّن")
    return value

# [+] إعدادات البوت الأساسية
BOT_TOKEN: str = get_env("BOT_TOKEN")
BOT_USERNAME: str = get_env("BOT_USERNAME", "UFOQ_BOT")
CHANNEL_ID: str = get_env("CHANNEL_ID", "@UFOQ_7")
ADMIN_ID: int = int(get_env("ADMIN_ID", "6689435577"))
PROMO_CHANNEL_ID: str = get_env("PROMO_CHANNEL_ID", "@ufoq_pre")

# [+] روابط الصور
MAIN_IMAGE_URL: str = get_env("MAIN_IMAGE_URL", "https://i.ibb.co/BHXgvYTF/x.jpg")
SUBSCRIPTION_IMAGE_URL: str = get_env("SUBSCRIPTION_IMAGE_URL", "https://i.ibb.co/Y7ggsNTN/x.jpg")

# [+] ملصق المعالجة
PROCESSING_STICKER_ID: str = get_env("PROCESSING_STICKER_ID", "CAACAgIAAxkBAAERmyhqZOIj8daLAqUE9ZJ8i3yDwVw05AACQQEAAs0bMAjx8GIY3_aWWD0E")

# [+] رابط المطور
DEVELOPER_LINK: str = get_env("DEVELOPER_LINK", "https://t.me/OlIiIl7")

# [+] الحد الأقصى لحجم الصورة (5 ميجابايت)
MAX_IMAGE_SIZE: int = int(get_env("MAX_IMAGE_SIZE", "5242880"))

# [+] إعدادات Supabase
SUPABASE_URL: str = get_env("SUPABASE_URL")
SUPABASE_KEY: str = get_env("SUPABASE_KEY")

# [+] إعدادات الوكيل (Proxy)
PROXY_ENABLED: bool = get_env("PROXY_ENABLED", "False").lower() == "true"
PROXY_TYPE: str = get_env("PROXY_TYPE", "socks5")
PROXY_HOST: str = get_env("PROXY_HOST", "")
PROXY_PORT: int = int(get_env("PROXY_PORT", "1080"))
PROXY_USER: str = get_env("PROXY_USER", "")
PROXY_PASS: str = get_env("PROXY_PASS", "")

# ============================================================
# [+] النصوص الثابتة - تم تحسينها لتكون أكثر وضوحاً وجاذبية
# ============================================================

WELCOME_TEXT: str = """
[*] مرحباً بك في بوت UFOQ [*]

البوت المتخصص في استخراج البرومبتات الاحترافية من الصور باستخدام أحدث تقنيات الذكاء الاصطناعي.

[+] استخدم الأزرار أدناه للبدء:
   • استخراج برومبت - حلل صورتك واحصل على وصف دقيق
   • تجميع نقاط - احصل على نقاط مجانية عبر الدعوات
   • أحدث البرومبتات - تصفح أحدث الإبداعات

[>] انطلق الآن واكتشف إمكانيات لا نهائية.
"""

POINTS_INFO_TEXT: str = """
[*] نظام النقاط والحوافز [*]

[+] نقاطك الحالية: {points}
[+] عدد المدعوين: {invited_count}

[#] كيف تحصل على نقاط إضافية؟
   • نقطة مجانية عند بدء استخدام البوت
   • نقطة إضافية لكل صديق يدعوه عبر رابطك

[>] رابط الدعوة الخاص بك:
<code>{invite_link}</code>

[!] انسخ الرابط وأرسله لأصدقائك لتجميع المزيد من النقاط.
"""

SUB_REQUIRED_TEXT: str = """
[!] اشتراك مطلوب للاستمرار [!]

للوصول إلى جميع ميزات البوت، يرجى الاشتراك في القناة الرسمية:

[>] <a href="https://t.me/UFOQ_7">@UFOQ_7</a>

[=] بعد الاشتراك، اضغط على زر التحقق أدناه.
"""

DEVELOPER_TEXT: str = """
[*] المطور والدعم الفني [*]

[+] تم تطوير هذا البوت بواسطة فريق محترف لتقديم أفضل تجربة في استخراج البرومبتات.

[>] للتواصل مع المطور:
<a href="https://t.me/OlIiIl7">@OlIiIl7</a>

[+] للإبلاغ عن مشكلة أو اقتراح تحسين، لا تتردد في التواصل.
"""

NO_POINTS_TEXT: str = """
[!] نقاط غير كافية [!]

تحتاج إلى نقطة واحدة على الأقل لاستخدام ميزة استخراج البرومبت.

[#] كيف تحصل على نقاط؟
   • ادعُ أصدقائك عبر رابطك الخاص
   • كل دعوة ناجحة تمنحك نقطة إضافية

[>] رابط الدعوة الخاص بك:
<code>{invite_link}</code>
"""

REQUEST_IMAGE_TEXT: str = """
[+] أرسل الصورة الآن [+]

قم بإرسال الصورة التي تريد استخراج البرومبت منها.

[~] سيتم تحليل الصورة خلال 10-30 ثانية.

[!] تأكد من أن الصورة واضحة وذات جودة جيدة للحصول على أفضل نتيجة.
"""

GIFT_ALREADY_USED: str = """
[!] انتهت صلاحية الهدية [!]

عذراً، تم استنفاد جميع الاستخدامات المتاحة لهذه الهدية.

[>] تابع البوت للحصول على هدايا جديدة في المستقبل.
"""

GIFT_SUCCESS_TEXT: str = """
[+] تهانينا! تم تفعيل الهدية بنجاح [+]

[+] حصلت على {points} نقطة إضافية من كود الهدية: <code>{code}</code>

[#] رصيدك الحالي محدّث تلقائياً.

[>] استخدم نقاطك لاستخراج برومبتات جديدة.
"""

ADMIN_PANEL_TEXT: str = """
[#] لوحة التحكم الإدارية [#]

اختر إحدى المجموعات التالية لإدارة البوت:

[+] إدارة النقاط: شحن أو سحب نقاط المستخدمين
[+] إدارة المستخدمين: حظر، فك حظر، أو عرض المحظورين
[+] روابط الهدية: إنشاء روابط هدايا بنقاط مجانية

[!] هذه اللوحة مخصصة للأدمن فقط.
"""

GIFT_CREATED_TEXT: str = """
[+] تم إنشاء رابط الهدية بنجاح [+]

[#] تفاصيل الهدية:
   • عدد النقاط: <b>{points}</b>
   • الحد الأقصى للمستفيدين: <b>{max_uses}</b>

[>] رابط الهدية:
<code>{link}</code>

[>] كود الهدية:
<code>{code}</code>

[!] شارك الرابط مع المستخدمين للحصول على نقاط مجانية.
"""

SYSTEM_PROMPT: str = """
A professional, visually balanced composition analyzed at maximum precision: analyze the overall composition framework first identifying the image aspect ratio, the rule of thirds alignment or golden ratio application, the negative space distribution, and the visual weight balance between all elements before describing individual components; the uploaded image features [product/person] positioned centrally with exact dominant color palette including tonal contrasts, primary secondary and accent colors with approximate hex values if digitally rendered, color temperature warm cool or neutral, saturation levels, and the color harmony scheme used complementary analogous triadic or monochromatic, gradient transitions color overlays or transparency effects; identify the precise spatial arrangement of every visual element, their relative positions, sizes, layering order, and implied direction vectors if motion is conveyed; detect and transcribe every visible text element individually placing each text within parentheses exactly as it appears in its precise location within the layout, preserving the original meaning feature or information conveyed, for Arabic text elements preserve the right-to-left reading direction maintain exact diacritical marks if present and note the calligraphic style or font category Kufic Naskh Thuluth etc without naming the specific font file; for logos consisting of a few letters or a single word, transform the letters themselves into thin graphic shapes in one or multiple solid colors on a plain white background, strictly 2D, maintaining strong visual balance for memorability and impact, preserve the original aspect ratio and letter spacing proportions, describe counter-shapes precisely, preserve baseline alignment and cap-height relationships between characters; if the user provides two keywords separated by a plus sign, merge the element or object with the brand name to generate a pictorial name logo where the element and name coexist in perfect visual harmony through professional positioning, shared object boundaries, and rich balanced composition, the element and text arranged in a breathtaking unforgettable layout that astonishes the viewer with its elegance and sophistication, placing the visual object first then the name; if the image depicts a person rely entirely on the uploaded image for all physical descriptions without mentioning hair, facial features, skin tone, or any personal identifiers, describing only body posture, gestures, clothing, and actions as visible in the uploaded image; if the image is a product advertisement reference only "the product in the uploaded image" without describing any product details, type, color, or specific features, however if a brand name or logo is visibly integrated into the product design itself transcribe it exactly as it appears without describing the product's physical attributes; specify lighting type, intensity, directionality, and mood only when relevant, describe shadows cast direction and softness; define camera angle or viewpoint precisely when applicable including focal length impression if discernible; state art style and realism level strictly as needed; include materials, textures, and micro-details only when they enhance clarity, describe surface textures with precision specifying glossiness level matte satin glossy mirror, surface irregularities smooth brushed hammered embossed, and material behavior under light absorption reflection refraction subsurface scattering, for fabric textures note the weave pattern drape behavior and fold geometry, identify micro-details that reveal production method such as pixelation edges for digital images, film grain structure for analog photography, print dot patterns for scanned materials, compression artifacts for web images, and brush stroke directions for hand-painted elements; outline background elements and spatial relationships if present; transcribe any visible text exactly including Arabic or English logos with precise fidelity even if outside standard fonts, without specifying the exact font name; mention exact image dimensions if provided; remove any visible designer credits, watermarks, copyright marks, or stock image overlays, if a watermark obscures a critical visual element describe what lies beneath based on visible surrounding context without inventing details; use bracketed placeholders [color], [name], [element], [text] only when information is genuinely missing or unreadable; output strictly one single line containing only the generated prompt, with no commentary, no extra text, and no formatting beyond the prompt itself.
"""