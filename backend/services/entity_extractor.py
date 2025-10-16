import os
import re
import json
from typing import Dict, List, Optional
from .scibox_client import get_scibox_client


def _normalize(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


class EntityExtractor:
    def __init__(self, kb_path: Optional[str] = None):
        self.client = None
        try:
            self.client = get_scibox_client()
        except Exception:
            self.client = None

        self.kb_path = kb_path or os.getenv("KB_PATH", "kb")
        self.entities = {}
        self.synonyms = {"category": {}, "subcategory": {}}

        e = os.path.join(self.kb_path, "entities.json")
        s = os.path.join(self.kb_path, "synonyms.json")
        if os.path.exists(e):
            try:
                with open(e, "r", encoding="utf-8") as f:
                    self.entities = json.load(f)
            except Exception:
                self.entities = {}
        if os.path.exists(s):
            try:
                with open(s, "r", encoding="utf-8") as f:
                    self.synonyms = json.load(f)
            except Exception:
                self.synonyms = {"category": {}, "subcategory": {}}

    def _match_by_synonyms(self, text: str, table: Dict[str, List[str]]) -> Optional[str]:
        t = _normalize(text)
        for canon, forms in table.items():
            for f in forms:
                if not f:
                    continue
                if _normalize(f) in t:
                    return canon
        return None

    def _match_by_list(self, text: str, items: List[str]) -> Optional[str]:
        t = _normalize(text)
        for it in items:
            if _normalize(it) in t:
                return it
        return None

    def extract(self, text: str) -> Dict[str, str]:
        if self.client:
            try:
                out = self.client.extract(text)
                if isinstance(out, dict) and out:
                    entities = dict(out)
                else:
                    entities = {}
            except Exception:
                entities = {}
        else:
            entities = {}

        cat = self._match_by_synonyms(text, self.synonyms.get("category", {}))
        if not cat:
            cat = self._match_by_list(text, self.entities.get("category", []))
        if cat:
            entities["category"] = cat

        sub = None
        sub_syn = self.synonyms.get("subcategory", {})
        if sub_syn:
            sub = self._match_by_synonyms(text, sub_syn)
        if not sub:
            sub_map = self.entities.get("subcategory_by_category", {})
            if entities.get("category") and entities["category"] in sub_map:
                sub = self._match_by_list(text, sub_map[entities["category"]])
            else:
                all_subs = []
                for arr in self.entities.get("subcategory_by_category", {}).values():
                    all_subs.extend(arr)
                sub = self._match_by_list(text, all_subs)
        if sub:
            entities["subcategory"] = sub

        pr = self._match_by_list(text, self.entities.get("priority", []))
        if pr:
            entities["priority"] = pr

        au = self._match_by_list(text, self.entities.get("audience", []))
        if au:
            entities["audience"] = au

        low = text.lower()
        if "product" not in entities:
            if re.search(r'pro|премиум|проф', low):
                entities["product"] = "pro"
        if "region" not in entities:
            if re.search(r'минск|беларус|by\b|byn|руб|₽', low):
                entities["region"] = "BY"
        if "issue" not in entities:
            if re.search(r'не прош(е|ё)л|откл|payment fail|списан.*не', low):
                entities["issue"] = "payment_failed"
        if "priority" not in entities:
            if re.search(r'срочно|критич|важно', low):
                entities["priority"] = "high"

        return entities
