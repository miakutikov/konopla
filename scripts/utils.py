"""
utils.py — Спільні утиліти для KONOPLA.UA pipeline скриптів.

Atomic JSON I/O для запобігання пошкодження файлів при крешах.
"""

import json
import os
import tempfile


def load_json(filepath, default=None):
    """Завантажує JSON файл. Повертає default якщо файл не існує або пошкоджений."""
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_json(filepath, data):
    """Атомарний запис JSON: спочатку tmp-файл, потім os.replace."""
    dirpath = os.path.dirname(filepath)
    os.makedirs(dirpath, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=dirpath, delete=False, suffix=".tmp", encoding="utf-8"
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, filepath)
