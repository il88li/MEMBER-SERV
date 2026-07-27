# ============================================================
# إعدادات البوت الأساسية
# ============================================================

BOT_TOKEN = "8998562807:AAG4GIpWf7qWLPuTpD0f-nGXYZEDOgZXIto"
BOT_USERNAME = "UFOQ_BOT"
CHANNEL_ID = "@UFOQ_7"
ADMIN_ID = 6689435577

# ============================================================
# قناة نشر البرومبتات
# ============================================================

PROMO_CHANNEL_ID = "@ufoq_pre"

# ============================================================
# روابط الصور والملصقات
# ============================================================

MAIN_IMAGE_URL = "https://i.ibb.co/BHXgvYTF/x.jpg"
SUBSCRIPTION_IMAGE_URL = "https://i.ibb.co/Y7ggsNTN/x.jpg"
PROCESSING_STICKER_ID = "CAACAgIAAxkBAAERmyhqZOIj8daLAqUE9ZJ8i3yDwVw05AACQQEAAs0bMAjx8GIY3_aWWD0E"
DEVELOPER_LINK = "https://t.me/OlIiIl7"
MAX_IMAGE_SIZE = 5242880

# ============================================================
# إعدادات Supabase (باستخدام المفتاح السري)
# ============================================================

SUPABASE_URL = "https://sthyookhxbaxqmuvqhps.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0aHlvb2toeGJheHFtdXZxaHBzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NDgyNzM2NywiZXhwIjoyMTAwNDAzMzY3fQ.GVHcULh7HA0sCGadk18oK5qzQmrllxm7QVQ5TgPBnQc"

# ============================================================
# إعدادات البروكسي (معطلة افتراضياً)
# ============================================================

PROXY_ENABLED = False
PROXY_TYPE = "socks5"
PROXY_HOST = ""
PROXY_PORT = 1080
PROXY_USER = ""
PROXY_PASS = ""

# ============================================================
# النصوص الثابتة
# ============================================================

WELCOME_TEXT = """
<b>🌟 مرحباً بك في بوت UFOQ</b>

يمكنك استخدام الأزرار أدناه:

• <b>استخراج برومبت</b> – تحليل الصور واستخراج وصف دقيق.
• <b>تجميع نقاط</b> – احصل على نقاط مجانية وادعُ أصدقائك.
• <b>أحدث البرومبتات</b> – تصفح أحدث البرومبتات المستخرجة.
• <b>المطور</b> – للتواصل مع فريق الدعم.
"""

POINTS_INFO_TEXT = """
<b>📊 نظام النقاط</b>

• نقطة مجانية عند البدء.
• نقطة إضافية لكل صديق تدعوه.
• رابط دعوتك: <code>{invite_link}</code>
• عدد المدعوين: {invited_count}
• نقاطك: <b>{points}</b>
"""

SUB_REQUIRED_TEXT = """
<b>⚠️ اشترك أولاً</b>

للاستمرار، اشترك في القناة:
<a href="https://t.me/UFOQ_7">@UFOQ_7</a>

ثم اضغط <b>تحقق</b>.
"""

DEVELOPER_TEXT = """
<b>👨‍💻 المطور</b>

<a href="https://t.me/OlIiIl7">@OlIiIl7</a>
"""

NO_POINTS_TEXT = """
<b>⛔ نقاط غير كافية</b>

تحتاج نقطة واحدة على الأقل.
ادعُ أصدقائك عبر رابطك:
<code>{invite_link}</code>
"""

REQUEST_IMAGE_TEXT = """
<b>📸 أرسل الصورة</b>

أرسل الصورة التي تريد استخراج البرومبت منها.
"""

GIFT_ALREADY_USED = "⚠️ انتهت صلاحية الهدية."
GIFT_SUCCESS_TEXT = "🎉 حصلت على {points} نقطة من {code}!"

ADMIN_PANEL_TEXT = """
<b>🔐 لوحة التحكم الإدارية</b>

استخدم الأزرار أدناه لإدارة البوت.
"""

GIFT_CREATED_TEXT = """
✅ تم إنشاء رابط الهدية بنجاح!

• عدد النقاط: <b>{points}</b>
• الحد الأقصى للمستفيدين: <b>{max_uses}</b>
• الرابط: <code>{link}</code>
• الكود: <code>{code}</code>
"""

SYSTEM_PROMPT = """A professional, visually balanced composition analyzed at maximum precision: analyze the overall composition framework first identifying the image aspect ratio, the rule of thirds alignment or golden ratio application, the negative space distribution, and the visual weight balance between all elements before describing individual components; the uploaded image features [product/person] positioned centrally with exact dominant color palette including tonal contrasts, primary secondary and accent colors with approximate hex values if digitally rendered, color temperature warm cool or neutral, saturation levels, and the color harmony scheme used complementary analogous triadic or monochromatic, gradient transitions color overlays or transparency effects; identify the precise spatial arrangement of every visual element, their relative positions, sizes, layering order, and implied direction vectors if motion is conveyed; detect and transcribe every visible text element individually placing each text within parentheses exactly as it appears in its precise location within the layout, preserving the original meaning feature or information conveyed, for Arabic text elements preserve the right-to-left reading direction maintain exact diacritical marks if present and note the calligraphic style or font category Kufic Naskh Thuluth etc without naming the specific font file; for logos consisting of a few letters or a single word, transform the letters themselves into thin graphic shapes in one or multiple solid colors on a plain white background, strictly 2D, maintaining strong visual balance for memorability and impact, preserve the original aspect ratio and letter spacing proportions, describe counter-shapes precisely, preserve baseline alignment and cap-height relationships between characters; if the user provides two keywords separated by a plus sign, merge the element or object with the brand name to generate a pictorial name logo where the element and name coexist in perfect visual harmony through professional positioning, shared object boundaries, and rich balanced composition, the element and text arranged in a breathtaking unforgettable layout that astonishes the viewer with its elegance and sophistication, placing the visual object first then the name; if the image depicts a person rely entirely on the uploaded image for all physical descriptions without mentioning hair, facial features, skin tone, or any personal identifiers, describing only body posture, gestures, clothing, and actions as visible in the uploaded image; if the image is a product advertisement reference only "the product in the uploaded image" without describing any product details, type, color, or specific features, however if a brand name or logo is visibly integrated into the product design itself transcribe it exactly as it appears without describing the product's physical attributes; specify lighting type, intensity, directionality, and mood only when relevant, describe shadows cast direction and softness; define camera angle or viewpoint precisely when applicable including focal length impression if discernible; state art style and realism level strictly as needed; include materials, textures, and micro-details only when they enhance clarity, describe surface textures with precision specifying glossiness level matte satin glossy mirror, surface irregularities smooth brushed hammered embossed, and material behavior under light absorption reflection refraction subsurface scattering, for fabric textures note the weave pattern drape behavior and fold geometry, identify micro-details that reveal production method such as pixelation edges for digital images, film grain structure for analog photography, print dot patterns for scanned materials, compression artifacts for web images, and brush stroke directions for hand-painted elements; outline background elements and spatial relationships if present; transcribe any visible text exactly including Arabic or English logos with precise fidelity even if outside standard fonts, without specifying the exact font name; mention exact image dimensions if provided; remove any visible designer credits, watermarks, copyright marks, or stock image overlays, if a watermark obscures a critical visual element describe what lies beneath based on visible surrounding context without inventing details; use bracketed placeholders [color], [name], [element], [text] only when information is genuinely missing or unreadable; output strictly one single line containing only the generated prompt, with no commentary, no extra text, and no formatting beyond the prompt itself."""