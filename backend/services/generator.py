from typing import List, Dict, Any
import re
import os

KB_ONLY = os.getenv("KB_ONLY", "1") == "1"
MIN_HIT_SCORE = float(os.getenv("MIN_HIT_SCORE", "0.000001"))

def scrub_pii(text: str) -> str:
    text = re.sub(r'\b\d{12,19}\b', '[CARD]', text)
    text = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)
    text = re.sub(r'\+?\d[\d\s()-]{7,}', '[PHONE]', text)
    return text

def extract_instruction_block(md: str) -> str:
    if not md:
        return ""
    m = re.search(r'^\s*##\s*Инструкция\s*/\s*Ответ\s*$(.*?)(^\s*##\s|\Z)',
                  md, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if m:
        body = m.group(1).strip()
        body = re.sub(r'^\s*\*\*.*?\*\*\s*$', '', body, flags=re.MULTILINE)
        return body.strip()
    m2 = re.search(r'^\s*##\s*Вопрос\s*$(.*?)(^\s*##\s|\Z)', md,
                   flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return md.strip()

TEMPLATE = (
    "Класс запроса: {intent}\n"
    "Извлеченные сущности: {entities}\n\n"
    "Рекомендация оператору:\n"
    "- Шаги решения: {steps}\n"
    "- Возможные причины: {causes}\n"
    f"- Что ответить клиенту (черновик):\n{{draft}}\n\n"
    "Источники:\n{sources}\n"
)

class RecommendationGenerator:
    def __init__(self, llm: str = "off"):
        self.llm = llm

    def generate(self, text: str, intent: str, entities: Dict[str, str], hits: List[Dict[str, Any]]):
        text = scrub_pii(text)
        good_hits = [h for h in hits if float(h.get("score", 0.0)) >= MIN_HIT_SCORE]
        if KB_ONLY:
            draft = self._kb_only_draft(good_hits)
        else:
            draft = self._hybrid_draft(text, intent, entities, good_hits)
        if KB_ONLY and not draft.strip():
            draft = ("Не найден подходящий ответ в базе знаний. "
                     "Пожалуйста, проверьте формулировку запроса или уточните данные в Excel-FAQ.")
        steps = [f"Сверьтесь с инструкцией: «{h['title']}»." for h in good_hits[:3]]
        causes = [f"Детали в «{h['title']}»." for h in good_hits[:3]]
        sources = "\n".join([f"- {h['title']} (KB:{h['doc_id']})" for h in good_hits]) if good_hits else "- (нет)"
        return TEMPLATE.format(
            intent=intent,
            entities=entities,
            steps="; ".join(steps) if steps else "—",
            causes="; ".join(causes) if causes else "—",
            draft=draft,
            sources=sources
        )

    def _kb_only_draft(self, hits: List[Dict[str, Any]]) -> str:
        pieces = []
        for h in hits[:3]:
            body = self._read_file_safe(h.get("path"))
            instr = extract_instruction_block(body)
            instr = (instr or "").strip()
            if instr:
                instr = instr[:2000].rstrip()
                pieces.append(instr)
        return ("\n\n---\n\n").join(pieces)

    def _hybrid_draft(self, text, intent, entities, hits):
        prod = entities.get("product", "ваш продукт/услуга")
        issue = entities.get("issue", "вопрос")
        region = entities.get("region", "ваш регион")
        priority = entities.get("priority", "обычный")
        return (
            f"Спасибо за обращение! Понимаю, что у вас {issue} по {prod}. "
            f"Зафиксировали обращение (приоритет: {priority}). Для {region} действуют шаги из инструкций выше."
        )

    @staticmethod
    def _read_file_safe(path: str) -> str:
        try:
            if not path:
                return ""
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
