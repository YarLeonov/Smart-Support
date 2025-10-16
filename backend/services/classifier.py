from typing import Dict

INTENTS = {
    "billing": ["оплат", "счет", "invoice", "платеж", "чек", "refund", "возврат", "byn"],
    "technical": ["не работает", "ошибка", "баг", "падает", "таймаут", "timeout", "ошибк"],
    "access": ["войти", "парол", "доступ", "логин", "2fa", "двухфактор"],
    "cards": ["карта", "картой", "visa", "mastercard", "mir"],
    "general": []
}

class Classifier:
    def classify(self, text: str, entities: Dict[str, str]) -> str:
        low = text.lower()
        for intent, keys in INTENTS.items():
            if any(k in low for k in keys):
                return intent
        if entities.get("issue") in ["payment_failed", "invoice_needed", "refund"]:
            return "billing"
        return "general"
