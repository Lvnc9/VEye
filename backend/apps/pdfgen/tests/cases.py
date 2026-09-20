"""Document fixtures shared by the golden-PDF generator (tools/make_golden_from_v1.py,
which feeds them to V_1.0's own renderer) and by test_golden.py (which loads the
same content into Postgres and renders it with the port).

Plain data, no Django imports, so the generator can import it on its own.
"""
from datetime import date

#: What the QR codes in the golden files point at — tests override
#: FRONTEND_BASE_URL to this.
FRONTEND = "https://veye.test"

SIGNERS = {
    "creater": ("محمد رضایی", "یک سمت تست"),
    "confirmer": ("داریوش معروفی", "کارشناس صنایع"),
    "approver": ("سام محمدی", "کارشناس IT"),
}

LONG_LINE = (
    "این یک بند بسیار طولانی است که عمداً بیش از یکصد و هفتاد نویسه نوشته شده تا رفتار شکستن خطوط "
    "بر اساس تعداد نویسه (و نه عرض واقعی متن) در نسخه اصلی حفظ شود؛ شامل کد ISO 9001:2015 و عدد 1404/01/19 "
    "و چند کلمهٔ دیگر برای رسیدن به طول لازم."
)

BODY = "\n".join(
    [
        "شرکت نمونه (سهامی عام) نظام مدیریت یکپارچه خود را بر اساس ISO 9001:2015 و ISO 14001:2015 مستقر نموده و "
        "خود را **متعهد** به ~~بهبود مستمر~~ و --رعایت الزامات-- می‌داند.",
        "",
        LONG_LINE,
        "بند سوم: مسئولیت اجرا با واحد PR-01 و پیگیری با کد WI-03-02 است.",
    ]
    + [f"خط شمارهٔ {i} از متن بلند برای رسیدن به شکستن صفحه — Line {i}" for i in range(1, 46)]
)

RESPONSIBILITY_ROWS = [
    ("مدیر برنامه ریزی", "ناظر کیفی", "تهیه و بازنگری این مستند"),
    ("کارشناس IT", "ناظر", "نگهداری و ارائه داده‌ها به کارکنان مربوط در زمان مقرر"),
    ("حسابدار", "", ""),
    ("", "ناظر مالی", "متن **مهم** برای آزمون شکستن خط: " + "کلمه " * 40),
]
RESPONSIBILITY_NOTES = ["یادداشت اول", "یادداشت دوم که کمی طولانی‌تر است " + "و ادامه دارد " * 12]

CASES = {
    # Mirrors the archived «نمونه-PR-01-01.pdf».
    "sample": dict(
        title="نمونه", group="PROCEDURE", number=1, revision=1, status="UNDER_CONTROL",
        day=date(2025, 4, 8), footnotes=("با احترام نظیر کارکنان محترم", "واحد برنامه ریزی"),
        logo=True, signers=("creater", "confirmer", "approver"),
        sections=[("short", ["1-هدف", "باقی اهداف"])],
    ),
    # Empty Attachment block, no logo/signatures/footnotes: the placeholder paths.
    "bare": dict(
        title="عنوان", group="POSTER", number=2, revision=1, status="UNDER_CONTROL",
        day=date(2025, 4, 8), footnotes=("", ""), logo=False, signers=(),
        sections=[("short", ["1-هدف", "نمونه ثانویه"]), ("long", "2-توضیحات", ""), ("attachments", [])],
    ),
    # Every block type, a second revision with frozen history, page overflow.
    "full": dict(
        title="روش اجرایی کنترل مستندات", group="INSTRUCTION", number=3, revision=2, status="OBSOLETE",
        day=date(2025, 6, 1), footnotes=("معاونت برنامه ریزی", "واحد سیستم‌ها و روش‌ها"),
        logo=True, signers=("creater", "approver"),
        previous_changes=[(date(2025, 3, 21), "ایجاد سند"), (date(2025, 3, 28), "اصلاح بند ۲")],
        sections=[
            ("short", ["1-هدف", "**هدف** این روش، ~~کنترل~~ --مستندات-- است.", "", "بند آخر"]),
            ("long", "2-شرح", BODY),
            ("responsibilities", RESPONSIBILITY_ROWS, RESPONSIBILITY_NOTES),
            ("changes", [(date(2025, 6, 1), "بازنگری کامل"), (date(2025, 6, 1), "افزودن ضمائم")]),
            ("attachments", [("فرم درخواست", "sample"), ("دستور کار PO", "bare")]),
        ],
    ),
    # A draft rendered as a watermarked preview: no validity mark yet.
    "draft_preview": dict(
        title="پیش نویس", group="FORM", number=4, revision=1, status="DRAFT",
        day=date(2025, 7, 1), footnotes=("", "واحد آزمون"), logo=False, signers=(),
        preview=True,
        sections=[("short", ["1-هدف", "متن پیش نویس"]), ("changes", [(date(2025, 7, 1), "نخستین نسخه")])],
    ),
}

PREFIX = {"POSTER": "PO", "PROCEDURE": "PR", "INSTRUCTION": "WI", "FORM": "FR"}


def code(case: dict, revision: int | None = None) -> str:
    return f"{PREFIX[case['group']]}-{case['number']:02d}-{(revision or case['revision']):02d}"
