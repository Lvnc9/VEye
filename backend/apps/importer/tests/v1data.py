"""A synthetic V_1.0 data directory (saves/ + img/ + index rows), built at test time.

Nothing here is real data: names, titles and signatures are invented, and the PNGs are
drawn with Pillow — so the fixtures can live in a public repository.
"""
import json
import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

URL = "https://files.invalid/user-files/"


def png(color=(10, 10, 120), size=(160, 70), alpha=False) -> bytes:
    mode = "RGBA" if alpha else "RGB"
    image = Image.new(mode, size, (0, 0, 0, 0) if alpha else (255, 255, 255))
    ImageDraw.Draw(image).line(
        [(8 + i * 3, size[1] / 2 + 18 * math.sin(i / 5)) for i in range((size[0] - 16) // 3)],
        fill=color + ((255,) if alpha else ()), width=3)
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def content_json(document_number, *, title="عنوان", date="1404/01/19", signers=("creater",), items=None, logo="logo.png",
                 foot=("پاورقی بالا", "پاورقی پایین"), signature_file=None):
    names = {"creater": ("نویسندهٔ نمونه", "کارشناس"), "confirmer": ("تاییدکنندهٔ نمونه", "معاون"), "approver": ("تصویب‌کنندهٔ نمونه", "مدیر عامل")}
    data = {"title": title, "logo_path": f"{URL}logos/{logo}" if logo else "", "document_number": document_number, "date": date,
            "qr_path": "./qr/x.png", "validation": "معتبر", "extra_header": "",
            "footnotes": {"footnote1": foot[0], "footnote2": foot[1]}, "dynamic_items": items or []}
    for role in ("creater", "confirmer", "approver"):
        if role in signers:
            file = signature_file or f"{document_number.rsplit('-', 1)[0]}-00{role}.png"
            data[role] = [names[role][0], names[role][1], f"{URL}{file}"]
        else:
            data[role] = ["", "", ""]
    return data


def full_items(attach_to="WI-01-01"):
    return [
        {"type": "Short Explanation", "content": ["1-هدف", "این یک نمونه است."]},
        {"type": "Long Explanation", "content": {"main_entry": "2-شرح", "main_textbox": "متن بلند **مهم**",
                                                "additional_textboxes": ["جعبهٔ اضافه"], "links": [f"{URL}f.pdf"]}},
        {"type": "Responsibilities", "content": {
            "options": ["مدیر برنامه", "Organiztion Post", "کارشناس", "", "ناظر کیفی", "SuperVisor", "", ""],
            "entries": ["شرح الف", "شرح ب", "شرح ج", "شرح د", "یادداشت"]}},
        {"type": "Changes Table", "content": {"rows": [
            {"column_number": "1", "edition": "01", "date": "1403/12/30", "content": {"text": "ردیف قدیمی", "type": "label", "previous_change": None}},
            {"column_number": "2", "edition": "02", "date": "1404/01/19", "content": {"text": "تغییر تازه", "type": "entry", "previous_change": None}}]}},
        {"type": "Attachment", "content": [], "all_labels": [["فرم پیوست", attach_to, "./qr/a.png"], ["ناموجود", "PO-09-01", "./qr/b.png"]]},
    ]


def row(title, group, code, review, valid, json_name="", category="Inside Organization"):
    return {"category": category, "title": title, "group": group, "review": review, "code": code, "valid": valid,
            "json_path": f"{URL}{json_name}".replace(" ", "%20") if json_name else "", "link": "", "simple_code": "1"}


def build(root: Path):
    """Write a V_1.0-style directory under `root`; return the index rows."""
    (root / "saves").mkdir(parents=True, exist_ok=True)
    (root / "img").mkdir(parents=True, exist_ok=True)

    def save(name, data):
        (root / "saves" / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    (root / "img" / "logo.png").write_bytes(png((20, 90, 160), (96, 96)))
    (root / "img" / "PR-01-00creater.png").write_bytes(png((10, 10, 120), alpha=True))      # transparent: must be flattened
    (root / "img" / "PR-01-00confirmer.png").write_bytes(png((120, 10, 10)))
    (root / "img" / "PR-01-00approver.png").write_bytes(png((10, 100, 10)))
    (root / "img" / "PR-01-01creater.png").write_bytes(b"this is not an image")            # corrupt: reported, not fatal

    save("روش الف-PR-01-01.json", content_json("PR-01-01", title="روش الف", signers=("creater", "confirmer", "approver"),
                                                items=full_items("WI-01-01")))
    save("روش الف-PR-01-02.json", content_json("PR-01-02", title="روش الف", signers=("creater",), date="1404/03/01", signature_file="PR-01-01creater.png",  # -> the corrupt file
                                                
                                                items=[{"type": "Short Explanation", "content": ["بازنگری دوم"]}]))
    save("دستور ب-WI-01-01.json", content_json("WI-01-01", title="دستور ب", signers=("creater", "confirmer"), logo=""))
    save("پیش نویس-FR-01-01.json", content_json("FR-01-00", title="فرم پیش نویس", signers=("creater",),   # "-00": not yet saved
                                                  items=[{"type": "Short Explanation", "content": ["پیش‌نویس"]}]))
    save("منسوخ-PO-01-01.json", content_json("PO-01-01", title="پوستر قدیمی", signers=()))
    save("دیگر-PO-03-01.json", content_json("PO-07-01", title="فایل اشتباه", signers=()))    # a different document's file

    return [
        row("روش الف", "روش اجرایی", "PR-01", "0-1", "vali", "روش الف-PR-01-01.json"),
        row("روش الف", "روش اجرایی", "PR-01", "0-2", "vali", "روش الف-PR-01-02.json"),
        row("دستور ب", "دستورالعمل", "WI-01", "0-1", "vali", "دستور ب-WI-01-01.json"),
        row("دستور بدون محتوا", "دستورالعمل", "WI-02", "0-0", "unknown"),
        row("پوستر قدیمی", "پوستر", "PO-01", "0-1", "outdated", "منسوخ-PO-01-01.json", category="Outside Organization"),
        row("فرم پیش نویس", "فرم", "FR-01", "0-1", "unknown", "پیش نویس-FR-01-01.json"),
        row("ردیف خراب", "پوستر", "PO-02", "x", "vali"),
        row("روش الف", "روش اجرایی", "PR-01", "0-1", "vali", "روش الف-PR-01-01.json"),                # duplicate of the first
        row("بدون فایل محتوا", "پوستر", "PO-05", "0-1", "vali", "does-not-exist.json"),
        row("فایل اشتباه", "پوستر", "PO-03", "0-1", "vali", "دیگر-PO-03-01.json"),
    ]
