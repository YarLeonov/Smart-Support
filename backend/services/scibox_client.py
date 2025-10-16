import os, json, requests

SCIBOX_BASE_URL = os.getenv("SCIBOX_BASE_URL", "https://llm.t1v.scibox.tech/v1")
SCIBOX_API_KEY = os.getenv("SCIBOX_API_KEY", "sk-daB5Q25N6xGt4V2q-MGOOQ")

EXTRACT_SYSTEM_PROMPT = (
    "Ты ассистент по разметке тикетов поддержки. "
    "Извлеки сущности и верни строго валидный JSON с ключами: "
    "product (строка|опц), issue (строка|опц), region (строка|опц), priority (low|normal|high|опц). "
    "Если нет данных — не указывай ключ."
    "Ответ выдавай на языке вороса."
    "Не учитывай регистр."
)

def _chat(messages, max_tokens=300):
    url = f"{SCIBOX_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {SCIBOX_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "Qwen2.5-72B-Instruct-AWQ", "messages": messages, "max_tokens": max_tokens, "stream": False}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return content

class RealSciboxClient:
    def extract(self, text: str):
        if not SCIBOX_API_KEY:
            raise RuntimeError("SCIBOX_API_KEY is not set")
        content = _chat([
            {"role":"system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role":"user", "content": f"Текст тикета:\n{text}\n\nВерни только JSON без пояснений."},
        ])
        start = content.find("{"); end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start:end+1])
        return {}

class MockSciboxClient:
    def extract(self, text: str):
        low = text.lower()
        out = {}
        if "pro" in low or "премиум" in low: out["product"] = "pro"
        if "оплат" in low or "payment" in low: out["issue"] = "payment_failed"
        if "минск" in low or "беларус" in low or "byn" in low: out["region"] = "BY"
        return out

def get_scibox_client():
    if SCIBOX_API_KEY:
        return RealSciboxClient()
    return MockSciboxClient()
