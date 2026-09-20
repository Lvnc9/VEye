"""V_1.0's local data directory: `saves/*.json` (document contents) and `img/` (logos and
signatures). Only local files are ever read (decided with the user: no downloading from
the Liara URLs).

File names come from rows and JSON files (the last segment of a URL), so they are
untrusted: only the bare name is used, it is looked up in a fixed directory, and the
resolved path must stay inside the import root (a symlink out is refused).
"""
import json
from pathlib import Path

from apps.core.text import normalize_letters

MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class V1Files:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self._listings: dict[str, dict[str, Path]] = {}

    @property
    def usable(self) -> bool:
        return (self.root / "saves").is_dir() or (self.root / "img").is_dir()

    def _listing(self, folder: str) -> dict:
        """{letter-normalised name: path}. V_1.0 file names mix Arabic and Persian yeh
        (its PDFs are «…اجرايي…»), so an exact match alone would miss files."""
        if folder not in self._listings:
            entries = {}
            directory = self.root / folder
            if directory.is_dir():
                for path in sorted(directory.iterdir()):
                    if path.is_file():
                        entries.setdefault(normalize_letters(path.name), path)
            self._listings[folder] = entries
        return self._listings[folder]

    def find(self, folder: str, name: str):
        """The file `name` in `folder`, or None. `name` is a bare file name."""
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            return None
        exact = self.root / folder / name
        candidate = exact if exact.is_file() else self._listing(folder).get(normalize_letters(name))
        if candidate is None:
            return None
        resolved = candidate.resolve()
        return resolved if self.root in resolved.parents else None

    def read_json(self, name: str):
        """(data, None) or (None, reason) for `saves/<name>`."""
        path = self.find("saves", name)
        if path is None:
            return None, "missing"
        try:
            if path.stat().st_size > MAX_JSON_BYTES:
                return None, "too_large"
            return json.loads(path.read_text(encoding="utf-8-sig")), None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None, "unreadable"

    def read_image(self, name: str):
        """(bytes, None) or (None, reason) for `img/<name>`."""
        path = self.find("img", name)
        if path is None:
            return None, "missing"
        try:
            if path.stat().st_size > MAX_IMAGE_BYTES:
                return None, "too_large"
            return path.read_bytes(), None
        except OSError:
            return None, "unreadable"
