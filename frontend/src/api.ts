export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function analyze(text: string) {
  const r = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ text })
  });
  if (!r.ok) {
    const msg = await r.text().catch(() => r.statusText);
    throw new Error(`Analyze failed: ${r.status} ${msg}`);
  }
  return r.json();
}

export async function previousReply(question: string, minScore = 0.95) {
  const r = await fetch(`${API_URL}/previous_reply`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ question, min_score: minScore })
  });
  if (!r.ok) {
    const msg = await r.text().catch(() => r.statusText);
    throw new Error(`previous_reply failed: ${r.status} ${msg}`);
  }
  return r.json();
}

export async function logInteraction(payload: {
  request_id: string;
  question: string;
  recommendation: string;
  operator_reply: string;
}) {
  if (!payload.operator_reply.trim().length) {
    throw new Error("Пустой ответ оператора запрещён к сохранению.");
  }
  const r = await fetch(`${API_URL}/log_interaction`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!r.ok) {
    const msg = await r.text().catch(() => r.statusText);
    throw new Error(`log_interaction failed: ${r.status} ${msg}`);
  }
  return r.json();
}
