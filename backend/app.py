import asyncio
import json
import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from services.retriever import KBRetriever
from services.generator import RecommendationGenerator
from services.classifier import Classifier
from services.entity_extractor import EntityExtractor
from services.telemetry import log_event, new_request_id
from services.logger import append_jsonl, find_previous_operator_reply

load_dotenv()
KB_ONLY = os.getenv("KB_ONLY", "1") == "1"  # включено по умолчанию

app = FastAPI(title="Smart Support - VTB{})".format(KB_ONLY))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# singletons
retriever = KBRetriever(kb_path="kb")
generator = RecommendationGenerator()
classifier = Classifier()
extractor = EntityExtractor()


class AnalyzeRequest(BaseModel):
    text: str
    channel: Optional[str] = "chat"
    locale: Optional[str] = "ru"
    meta: Optional[dict] = None


class InteractionLogRequest(BaseModel):
    request_id: str
    question: str
    recommendation: str
    operator_reply: str
    meta: Optional[dict] = None


class PreviousReplyRequest(BaseModel):
    question: str
    min_score: float = 0.95


@app.get("/health")
def health():
    return {"status": "ok", "kb_size": len(retriever.meta), "kb_only": KB_ONLY}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    req_id = new_request_id()
    log_event("incoming", request_id=req_id, text=req.text)

    # 1) Entities
    entities = extractor.extract(req.text)

    # 2) Intent
    intent = classifier.classify(req.text, entities)

    # 3) Retrieve
    hits = retriever.retrieve(req.text, entities=entities, top_k=5)

    # 4) Generate (строго из KB)
    recommendation = generator.generate(req.text, intent=intent, entities=entities, hits=hits)

    payload = {
        "request_id": req_id,
        "intent": intent,
        "entities": entities,
        "hits": hits,
        "recommendation": recommendation,
        "kb_only": KB_ONLY,
    }
    log_event("response", request_id=req_id, payload=payload)

    # ЛОГ: итог one-shot анализа
    append_jsonl({
        "event": "analyze_result",
        "request_id": req_id,
        "question": req.text,
        "entities": entities,
        "intent": intent,
        "hits": [h.get("doc_id") for h in hits],
        "recommendation": recommendation,
    })

    return JSONResponse(payload)


@app.post("/log_interaction")
def log_interaction(req: InteractionLogRequest):
    # сохраняем финальный ответ оператора
    append_jsonl({
        "event": "operator_reply",
        "request_id": req.request_id,
        "question": req.question,
        "recommendation": req.recommendation,
        "operator_reply": req.operator_reply,
        "meta": req.meta or {},
    })
    return {"status": "ok"}


@app.post("/previous_reply")
def previous_reply(req: PreviousReplyRequest):
    hit = find_previous_operator_reply(req.question, req.min_score)
    return {"found": bool(hit), "match": hit}


@app.websocket("/ws/assist")
async def ws_assist(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            content = json.loads(data)
            text = content.get("text", "")
            req_id = new_request_id()

            await ws.send_json({"phase": "start", "request_id": req_id})

            entities = extractor.extract(text)
            await ws.send_json({"phase": "entities", "entities": entities})

            intent = classifier.classify(text, entities)
            await ws.send_json({"phase": "intent", "intent": intent})

            hits = retriever.retrieve(text, entities=entities, top_k=5)
            for i, h in enumerate(hits):
                await ws.send_json({"phase": "hit", "rank": i + 1, "hit": h})
                await asyncio.sleep(0.02)

            recommendation = generator.generate(text, intent=intent, entities=entities, hits=hits)
            await ws.send_json({"phase": "recommendation", "recommendation": recommendation})

            # ЛОГ: итог WS-рекомендации
            append_jsonl({
                "event": "ws_recommendation",
                "request_id": req_id,
                "question": text,
                "entities": entities,
                "intent": intent,
                "hits": [h.get("doc_id") for h in hits],
                "recommendation": recommendation,
            })

            await ws.send_json({"phase": "end"})
    except WebSocketDisconnect:
        pass
