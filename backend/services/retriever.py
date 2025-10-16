import os
import glob
import json
import re
from typing import Dict, Optional, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def strip_front_matter(md: str) -> str:
    """Убираем YAML-фронтматтер вида --- ... --- в начале файла."""
    if not md:
        return md
    return re.sub(r'^\s*---[\s\S]*?---\s*', '', md, count=1, flags=re.MULTILINE)

def extract_instruction_block(md: str) -> str:
    """Достаём содержимое раздела '## Инструкция / Ответ'. Если нет — fallback на весь текст без служебных заголовков."""
    if not md:
        return ""
    # ищем «Инструкция / Ответ»
    m = re.search(r'^\s*##\s*Инструкция\s*/\s*Ответ\s*$(.*?)(^\s*##\s|\Z)',
                  md, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if m:
        body = m.group(1).strip()
    else:
        # fallback: после '## Вопрос'
        m2 = re.search(r'^\s*##\s*Вопрос\s*$(.*?)(^\s*##\s|\Z)', md,
                       flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
        body = (m2.group(1) if m2 else md).strip()

    # вычищаем жирные служебные строки «**Категория:** …», «**Подкатегория:** …»
    body = re.sub(r'^\s*\*\*\s*Категория\s*:\s*\*\*.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    body = re.sub(r'^\s*\*\*\s*Подкатегория\s*:\s*\*\*.*$', '', body, flags=re.MULTILINE | re.IGNORECASE)
    return body.strip()

def clean_snippet_from_file(path: str, limit: int = 600) -> str:
    """Читает файл, убирает фронтматтер, достаёт блок 'Инструкция / Ответ' и обрезает до limit."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            md = f.read()
    except Exception:
        return ""
    md = strip_front_matter(md)
    body = extract_instruction_block(md)
    body = body.strip()
    if len(body) > limit:
        body = body[:limit].rstrip() + "…"
    return body


class KBRetriever:
    """
    Если есть index.json — используем его (path, title, meta),
    иначе сканируем kb/articles/*.md.
    TF-IDF строим по расширенному тексту (мета+тело), но сниппет
    на выдаче формируем из чистого 'Инструкция / Ответ'.
    """

    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self.docs: List[str] = []
        self.meta: List[Dict] = []
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=100_000)
        self._matrix = None
        self._load()

    def _load_from_index(self, index_path: str):
        with open(index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        self.docs = []
        self.meta = []
        for row in idx:
            doc_id = row.get("doc_id") or row.get("id") or os.path.basename(row.get("path", "")) or ""
            title = row.get("title") or doc_id
            rel_path = row.get("path") or os.path.join("articles", doc_id)
            abs_path = os.path.join(self.kb_path, rel_path)

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    body = f.read()
            except Exception:
                body = ""

            # расширяем текст для индексации (title + мета + тело без фронтматтера)
            enrich = " ".join([
                title,
                row.get("category", "") or "",
                row.get("subcategory", "") or "",
                row.get("question_example", "") or "",
                row.get("priority", "") or "",
                row.get("audience", "") or "",
            ])
            body_for_index = strip_front_matter(body)
            fulltext = (enrich + "\n\n" + body_for_index).strip()

            self.docs.append(fulltext)
            self.meta.append({
                "doc_id": doc_id,
                "title": title,
                "path": abs_path,
                "category": row.get("category", ""),
                "subcategory": row.get("subcategory", ""),
                "priority": row.get("priority", ""),
                "audience": row.get("audience", ""),
                "question_example": row.get("question_example", ""),
            })

    def _load_from_glob(self):
        articles = glob.glob(os.path.join(self.kb_path, "articles", "*.md"))
        self.docs = []
        self.meta = []
        for p in articles:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    body = f.read()
            except Exception:
                body = ""
            title = os.path.basename(p).replace(".md", "").replace("_", " ").title()
            body_for_index = strip_front_matter(body)
            self.docs.append(title + "\n\n" + body_for_index)
            self.meta.append({"doc_id": os.path.basename(p), "title": title, "path": p})

    def _load(self):
        index_path = os.path.join(self.kb_path, "index.json")
        if os.path.exists(index_path):
            self._load_from_index(index_path)
        else:
            self._load_from_glob()
        self._matrix = self._vectorizer.fit_transform(self.docs) if self.docs else None

    def retrieve(self, query: str, entities: Optional[Dict[str, str]] = None, top_k: int = 5):
        if self._matrix is None:
            return []
        q = query
        if entities:
            kv = " ".join([f"{k}:{v}" for k, v in entities.items() if v])
            if kv:
                q = f"{query} {kv}"

        q_vec = self._vectorizer.transform([q])
        sims = cosine_similarity(q_vec, self._matrix)[0]
        order = sims.argsort()[::-1][:top_k]

        results = []
        for idx in order:
            m = self.meta[idx]
            # ✅ формируем «чистый» сниппет из файла
            snippet = clean_snippet_from_file(m.get("path"), limit=600)
            results.append({
                "doc_id": m.get("doc_id"),
                "title": m.get("title"),
                "score": float(sims[idx]),
                "snippet": snippet,
                "path": m.get("path"),
            })
        return results
