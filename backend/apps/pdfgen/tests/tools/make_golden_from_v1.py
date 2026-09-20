"""Regenerate tests/fixtures/golden/*.pdf with V_1.0's OWN code.

The golden PDFs are the oracle for test_golden.py: they are produced by feeding
each case in tests/cases.py, as V_1.0-format JSON, through the original
`Provider.extract_from_json` + `Provider.deliver_to_pdf` (deliver_convert.py +
to_make_pdf.py, unmodified), with ReportLab in `invariant` mode so the bytes are
reproducible. The port must reproduce them exactly.

Only network access and the viewer launch are stubbed. Run inside the backend
container (it has the pinned ReportLab / bidi / reshaper):

    docker compose cp <V_1.0>/other_folder backend:/tmp/v1/other_folder
    docker compose cp <V_1.0>/Vazir.ttf backend:/tmp/v1/Vazir.ttf     # repo-root pair
    docker compose cp <V_1.0>/Vazir-Bold.ttf backend:/tmp/v1/Vazir-Bold.ttf
    docker compose exec -T backend python -m apps.pdfgen.tests.tools.make_golden_from_v1 --v1 /tmp/v1

Two intentional normalisations of a stock V_1.0 run, neither of which changes a
single drawn pixel:
  * V_1.0 seeds its module-level `SHORT` buffer with " ", so the first Short block
    of a process gets a stray leading space; the port has no such global, so it is
    zeroed here.
  * V_1.0 hands the signature to `drawImage` as a *path*, which ReportLab names
    (`/FormXob.<md5>`) by hashing the path; the port has bytes, and ReportLab
    hashes those instead. Wrapping the path in an ImageReader makes the original
    name it the same way, so the files can be compared byte for byte.
"""
import argparse
import importlib
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

from apps.pdfgen.qr import qr_png
from apps.pdfgen.tests import cases as C

HERE = Path(__file__).resolve().parent.parent
FIXTURES = HERE / "fixtures"
URL = "https://files.test/"


def jalali(day):
    import jdatetime

    return jdatetime.date.fromgregorian(date=day).strftime("%Y/%m/%d")


def v1_json(name, case, previous_json_by_url, workdir):
    """A V_1.0 saves/*.json for `case` (shapes: utils.py:507-655)."""
    whole = C.code(case)
    img = workdir / "img"
    (workdir / "qr").mkdir(exist_ok=True)
    img.mkdir(exist_ok=True)

    def qr_file(target_code):
        path = workdir / "qr" / f"{target_code}.png"
        path.write_bytes(qr_png(f"{C.FRONTEND}/verify/{target_code}"))
        return f"./qr/{target_code}.png"

    logo_path = ""
    if case["logo"]:
        shutil.copy(FIXTURES / "logo.png", img / "logo.png")
        logo_path = URL + "logos/logo.png"

    signers = {}
    for role in ("creater", "confirmer", "approver"):
        if role in case["signers"]:
            shutil.copy(FIXTURES / f"sign_{role}.png", img / f"{whole}{role}.png")
            signers[role] = [*C.SIGNERS[role], f"{URL}user-files/{whole}{role}.png"]
        else:
            signers[role] = ["", "", ""]

    items = []
    for section in case["sections"]:
        kind = section[0]
        if kind == "short":
            items.append({"type": "Short Explanation", "content": section[1]})
        elif kind == "long":
            items.append({"type": "Long Explanation", "content": {
                "main_entry": section[1], "main_textbox": section[2], "additional_textboxes": [], "links": []}})
        elif kind == "responsibilities":
            rows, notes = section[1], section[2]
            options = [r[0] for r in rows] + [r[1] for r in rows]
            entries = [r[2] for r in rows] + list(notes)
            items.append({"type": "Responsibilities", "content": {"options": options, "entries": entries}})
        elif kind == "changes":
            items.append({"type": "Changes Table", "content": {"rows": [
                {"column_number": str(i), "edition": f"{case['revision']:02d}", "date": jalali(d),
                 "content": {"text": t, "type": "entry", "previous_change": None}}
                # Numbering continues across revisions (the earlier rows are prepended at PDF time).
                for i, (d, t) in enumerate(section[1], start=1 + len(case.get("previous_changes", [])))]}})
        elif kind == "attachments":
            labels = []
            for caption, key in section[1]:
                target = C.code(C.CASES[key])
                labels.append([caption, target, qr_file(target)])
            items.append({"type": "Attachment", "content": [], "all_labels": labels})

    return {
        "title": case["title"], "logo_path": logo_path, "document_number": whole,
        "date": jalali(case["day"]), "qr_path": qr_file(whole),
        "creater": signers["creater"], "approver": signers["approver"], "confirmer": signers["confirmer"],
        "validation": {"UNDER_CONTROL": "معتبر", "OBSOLETE": "منسوخ"}.get(case["status"], ""),
        "extra_header": "", "footnotes": {"footnote1": case["footnotes"][0], "footnote2": case["footnotes"][1]},
        "dynamic_items": items,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True, help="dir holding other_folder/, Vazir.ttf, Vazir-Bold.ttf")
    args = parser.parse_args()

    # No network in an oracle run: V_1.0 GETs the previous revision's JSON.
    responses = {}
    requests = types.ModuleType("requests")

    def fake_get(url, *a, **k):
        if url not in responses:
            raise RuntimeError(f"unexpected download {url}")
        return types.SimpleNamespace(content=responses[url])

    requests.get = fake_get
    sys.modules["requests"] = requests

    sys.path.insert(0, args.v1)
    open(Path(args.v1) / "other_folder" / "__init__.py", "a").close()
    from reportlab import rl_config
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    rl_config.invariant = 1
    original_draw_image = canvas.Canvas.drawImage

    def draw_image(self, image, *a, **k):
        return original_draw_image(self, ImageReader(image) if isinstance(image, str) else image, *a, **k)

    canvas.Canvas.drawImage = draw_image
    convert = importlib.import_module("other_folder.deliver_convert")
    convert.subprocess.run = lambda *a, **k: None  # the viewer launch
    convert.sys.exit = lambda *a: None

    out = HERE / "fixtures" / "golden"
    out.mkdir(exist_ok=True)
    for name, case in C.CASES.items():
        workdir = Path(tempfile.mkdtemp(prefix=f"golden-{name}-"))
        for font in ("Vazir.ttf", "Vazir-Bold.ttf"):  # PDFMaker opens "./Vazir.ttf"
            shutil.copy(Path(args.v1) / font, workdir / font)
        os.chdir(workdir)
        (workdir / "saves").mkdir()

        if case["revision"] > 1:
            # The previous revision's Changes Table, as V_1.0 fetched it.
            prev = dict(case, revision=case["revision"] - 1, day=case["previous_changes"][0][0],
                        sections=[("changes", case["previous_changes"])], logo=False, signers=(), previous_changes=[])
            first, second = f"{case['revision'] - 1:02d}"
            key = f"https://baravord24.storage.c2.liara.space/user-files/{case['title'].replace(' ', '%20')}-{C.PREFIX[case['group']]}-{case['number']:02d}-{first}{second}.json"
            os.makedirs(workdir / "check", exist_ok=True)
            responses[key] = json.dumps(v1_json(name + "_prev", prev, {}, workdir), ensure_ascii=False).encode()

        path = workdir / "saves" / f"{name}.json"
        path.write_text(json.dumps(v1_json(name, case, responses, workdir), ensure_ascii=False), encoding="utf-8")

        convert.SHORT = ""
        provider = convert.Provider(str(path))
        provider.extract_from_json()
        convert.SHORT = ""
        convert.Provider.deliver_to_pdf(preview=case.get("preview", False))

        produced = workdir / f"{case['title']}-{C.code(case)}.pdf"
        shutil.copy(produced, out / f"{name}.pdf")
        print("wrote", out / f"{name}.pdf", produced.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
