import os
import json
import time
import threading
import difflib
import re
from typing import Optional, Dict, Any, Iterator

# Директория и файл логов можно изменить через переменную окружения LOG_DIR
_LOG_DIR = os.getenv("LOG_DIR", "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "interactions.jsonl")

_lock = threading.Lock()
os.makedirs(_LOG_DIR, exist_ok=True)

def append_jsonl(record: Dict[str, Any]) -> None:
    """Пишем одну запись JSON в конец файла (JSONL-формат)."""
    record = {**record, "ts": time.time()}
    line = json.dumps(record, ensure_ascii=False)
    with _lock:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _iter_logs() -> Iterator[Dict[str, Any]]:
    if not os.path.exists(_LOG_FILE):
        return iter(())
    with open(_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue

def find_previous_operator_reply(question: str, min_score: float = 0.9) -> Optional[Dict[str, Any]]:
    """
    Возвращает последнюю запись с НЕпустым ответом оператора (operator_reply)
    для аналогичного вопроса. Никаких fallback на черновики рекомендаций.

    Сходство считается по difflib.SequenceMatcher (ratio 0..1) между
    нормализованными строками вопроса из запроса и вопроса в логе.
    """
    qn = _norm(question)
    best = None
    best_score = 0.0

    for rec in _iter_logs():
        # нас интересуют только записи, где оператор сохранял свой ответ
        if rec.get("event") != "operator_reply":
            continue

        q = rec.get("question") or ""
        op = (rec.get("operator_reply") or "").strip()
        if not op:
            continue

        score = difflib.SequenceMatcher(a=qn, b=_norm(q)).ratio()
        if score < min_score:
            continue

        if score > best_score:
            best = {
                "matched_question": q,
                "operator_reply": op,
                "score": score,
                "request_id": rec.get("request_id"),
                "ts": rec.get("ts"),
                "source": "operator",  # для явности
            }
            best_score = score

    return best
