import React, { useState } from 'react'

type PreviousReply = {
  matched_question: string
  operator_reply: string
  score: number
  request_id?: string
  ts?: number
} | null

type Hit = {
  doc_id: string
  title: string
  score: number
  snippet: string
  path: string
}

const API = (import.meta as any).env.VITE_API_URL || 'http://127.0.0.1:8000'
const MIN_SCORE = 0.000001 // скрываем совпадения с релевантностью, по сути, 0.0%

// простой uuid
function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// fetch с таймаутом (20s)
async function postJSON(path: string, payload: any, timeoutMs = 20000) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(API + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    })
    if (!res.ok) {
      const msg = await res.text().catch(() => res.statusText)
      throw new Error(`${path} failed: ${res.status} ${msg}`)
    }
    return res.json()
  } finally {
    clearTimeout(t)
  }
}

export default function App() {
  const [text, setText] = useState('')
  const [requestId, setRequestId] = useState<string>(uuid())

  const [hits, setHits] = useState<Hit[]>([])
  const [operatorReply, setOperatorReply] = useState<string>('')          // финальный ответ оператора
  const [previousReply, setPreviousReply] = useState<PreviousReply>(null) // «Ранее отвечали»

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string>('')

  function resetState() {
    setHits([])
    setPreviousReply(null)
    setError(null)
    setStatus('')
  }

  async function fetchPreviousReplyUI(q: string) {
    try {
      setStatus(s => s ? s + ' · previous_reply…' : 'previous_reply…')
      const j = await postJSON('/previous_reply', { question: q, min_score: 0.85 })
      if (j.found && j.match?.operator_reply) {
        setPreviousReply(j.match)
        setStatus(s => s + ' ✓')
      } else {
        setPreviousReply(null)
        setStatus(s => s + ' ∅')
      }
    } catch (e: any) {
      console.error('previous_reply error:', e)
      setStatus(s => s + ' ✗')
    }
  }

  const runQuery = async () => {
    if (!text.trim()) return
    resetState()

    const provisionalId = uuid()
    setRequestId(provisionalId)
    setLoading(true)
    setError(null)
    setStatus('POST /analyze…')

    try {
      const j = await postJSON('/analyze', { text: text.trim() })
      setRequestId(j.request_id || provisionalId)
      setHits(j.hits || [])
      setStatus('Ответ получен · подтягиваю «Ранее отвечали»')
      await fetchPreviousReplyUI(text.trim())
    } catch (e: any) {
      console.error('analyze error:', e)
      setError(e?.message || 'Ошибка запроса')
      setStatus('Ошибка при вызове /analyze')
    } finally {
      setLoading(false)
    }
  }

  const saveLog = async () => {
    if (!operatorReply.trim()) {
      alert('Нельзя сохранить пустой ответ оператора.')
      return
    }
    if (!requestId) {
      alert('Нет request_id для лога.')
      return
    }
    try {
      const res = await postJSON('/log_interaction', {
        request_id: requestId,
        question: text.trim(),
        recommendation: '(выбранный ответ вручную)',
        operator_reply: operatorReply.trim(),
        meta: { hits: hits.map(h => h.doc_id) }
      })
      console.log('log_interaction OK:', res)
      alert('Ответ сохранён.')
      await fetchPreviousReplyUI(text.trim())
    } catch (e: any) {
      console.error('log_interaction error:', e)
      alert(e?.message || 'Не удалось сохранить ответ.')
    }
  }

  // выбрать любой ответ и перенести в «Ответ оператора»
  const selectAnswer = (answerText: string) => {
    const clean = (answerText || '').trim()
    if (!clean) return
    setOperatorReply(clean)
    // прокрутка к полю «Ответ оператора»
    requestAnimationFrame(() => {
      const el = document.getElementById('operator-reply')
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  const isQueryDisabled = loading || !text.trim().length
  const visibleHits = hits.filter(h => (h.score ?? 0) > MIN_SCORE) // ← фильтрация «нулевых»

  return (
    <div style={{fontFamily:'Inter, system-ui, sans-serif', maxWidth:1000, margin:'40px auto', padding:'0 16px'}}>

      {/* Вопрос клиента — с кнопкой "Запрос" в шапке справа */}
      <div style={{padding:14, border:'1px solid #E5E7EB', borderRadius:12, background:'#FFFFFF'}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8}}>
          <div style={{fontSize:14, fontWeight:700}}>Вопрос клиента</div>
          <button
            onClick={runQuery}
            disabled={isQueryDisabled}
            title={!text.trim().length ? 'Введите вопрос' : ''}
            style={{
              padding:'8px 12px',
              borderRadius:8,
              border:'1px solid #2F6FEB',
              background: isQueryDisabled ? '#AFC6FF' : '#2F6FEB',
              color:'#fff',
              fontWeight:700,
              cursor: isQueryDisabled ? 'not-allowed' : 'pointer',
              opacity: isQueryDisabled ? 0.85 : 1
            }}>
            {loading ? 'Обрабатываю…' : 'Запрос'}
          </button>
        </div>
        <textarea
          style={{
            width:'100%', minHeight:50, padding:12,
            border:'1px solid #E5E7EB', borderRadius:10, outline:'none', background:'#FAFAFA'
          }}
          value={text}
          onChange={e=>setText(e.target.value)}
          placeholder="Опишите проблему клиента…"
        />

        {/* Ошибка и статус под блоком вопроса */}
        {error && (
          <div style={{marginTop:10, color:'#B00020', fontWeight:700}}>
            {error}
          </div>
        )}
        {status && !error && (
          <div style={{marginTop:8, fontSize:12, color:'#6B7280'}}>
            {status}
          </div>
        )}
      </div>

      {/* Рекомендованный ответ: сначала «Ранее отвечали», затем — ответы из KB по релевантности (после фильтра) */}
      <div style={{marginTop:16, padding:14, border:'1px solid #E5E7EB', borderRadius:12, background:'#FFFFFF'}}>
        <div style={{fontSize:14, fontWeight:700, marginBottom:8}}>Рекомендованный ответ</div>

        {/* 1) Ранее отвечали — всегда первым (если есть) */}
        {previousReply && (
          <div style={{
            marginBottom:10, padding:12,
            background:'#E9F7EF', border:'1px solid #CDEFD9', borderRadius:12, color:'#1E7E34'
          }}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6}}>
              <div style={{fontWeight:800}}>Ранее отвечали</div>
              <button
                onClick={() => selectAnswer(previousReply.operator_reply)}
                style={{
                  padding:'6px 10px', borderRadius:8,
                  border:'1px solid #16A34A', background:'#16A34A', color:'#fff', fontWeight:700, cursor:'pointer'
                }}
              >
                Выбрать этот ответ
              </button>
            </div>
            <div style={{whiteSpace: 'pre-wrap'}}>{previousReply.operator_reply}</div>
            <div style={{fontSize: 12, opacity: .7, marginTop: 6}}>
              Совпадение: {(previousReply.score * 100).toFixed(0)}% · request_id: {previousReply.request_id || '—'}
            </div>
          </div>
        )}

        {/* 2) Ответы из KB — по релевантности (после фильтра) */}
        <div style={{display:'grid', gap:10}}>
          {visibleHits.map((h) => (
            <div key={h.doc_id} style={{
              background:'#F8FAFC', border:'1px solid #E2E8F0', borderRadius:12, padding:12
            }}>
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6}}>
                <div style={{fontWeight:700}}>{h.title}</div>
                <button
                  onClick={() => selectAnswer(h.snippet)}
                  style={{
                    padding:'6px 10px', borderRadius:8,
                    border:'1px solid #2F6FEB', background:'#2F6FEB', color:'#fff', fontWeight:700, cursor:'pointer'
                  }}
                >
                  Выбрать этот ответ
                </button>
              </div>
              <div style={{whiteSpace:'pre-wrap'}}>{h.snippet}</div>
              <div style={{fontSize:12, opacity:.6, marginTop:6}}>
                Релевантность: {((h.score ?? 0) * 100).toFixed(1)}%
              </div>
            </div>
          ))}

          {/* Если ничего не прошло фильтр и нет «Ранее отвечали» */}
          {!previousReply && visibleHits.length === 0 && (
            <div style={{
              padding: 12, borderRadius: 10, background: '#F3F4F6',
              border: '1px solid #E5E7EB', color: '#374151'
            }}>
              Подходящих ответов не найдено. Уточните формулировку запроса или обновите Excel-FAQ.
            </div>
          )}
        </div>
      </div>

      {/* Ответ оператора — с кнопкой справа в шапке */}
      <div style={{marginTop:12, padding:14, border:'1px solid #E5E7EB', borderRadius:12, background:'#FFFFFF'}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8}}>
          <div style={{fontSize:14, fontWeight:700}}>Ответ оператора</div>
          <button
            onClick={async () => {
              if (!operatorReply.trim()) return
              await saveLog()
            }}
            disabled={!operatorReply.trim()}
            style={{
              padding:'8px 12px',
              borderRadius:8,
              border:'1px solid #16A34A',
              background: !operatorReply.trim() ? '#A7F3D0' : '#16A34A',
              color:'#fff',
              fontWeight:700,
              cursor: !operatorReply.trim() ? 'not-allowed' : 'pointer',
              opacity: !operatorReply.trim() ? 0.85 : 1
            }}>
            Сохранить ответ
          </button>
        </div>
        <textarea
          id="operator-reply"
          value={operatorReply}
          onChange={e=>setOperatorReply(e.target.value)}
          placeholder="Напишите ваш финальный ответ клиенту…"
          style={{width:'100%', minHeight:140, padding:12, border:'1px solid #D1D5DB', borderRadius:10, background:'#FFFFFF', whiteSpace:'pre-wrap'}}
        />
        <div style={{marginTop:8, fontSize:12, opacity:.6}}>request_id: {requestId}</div>
      </div>
    </div>
  )
}
