import React, { useState, useEffect, useRef, useCallback } from 'react'
import { listManuals, streamQuery, getHealth } from './utils/api'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatInput from './components/ChatInput'
import { Message, TypingIndicator } from './components/Message'
import { BookOpen } from 'lucide-react'

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-4">
      <div className="w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20
                      flex items-center justify-center">
        <BookOpen size={24} className="text-blue-400" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-gray-300">Ask your machine manual</h2>
        <p className="text-sm text-gray-600 mt-1 max-w-xs">
          Ask technical questions about your industrial machinery in natural language.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-2 text-xs text-gray-500 max-w-sm">
        {[
          '⚡ Self-RAG pipeline with answer validation',
          '📖 Source citations with page numbers',
          '🔍 Semantic search with relevance filtering',
          '🛡️ Hallucination detection & extractive fallback',
        ].map(f => (
          <div key={f} className="px-3 py-2 rounded-md border border-gray-800 bg-gray-900/30">{f}</div>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  const [manuals, setManuals] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [manualsLoading, setManualsLoading] = useState(false)
  const [health, setHealth] = useState(null)
  const bottomRef = useRef(null)
  const abortRef = useRef(null)

  // ── Fetch manuals ─────────────────────────────────────────────────────────

  const fetchManuals = useCallback(async () => {
    setManualsLoading(true)
    try {
      const res = await listManuals()
      const list = res.data.manuals
      setManuals(list)
      // Auto-select all on first load
      if (selectedIds.length === 0 && list.length > 0) {
        setSelectedIds(list.map(m => m.manual_id))
      }
    } catch {
      // backend may not be running yet
    } finally {
      setManualsLoading(false)
    }
  }, [])

  // ── Health polling ────────────────────────────────────────────────────────

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await getHealth()
        setHealth(res.data)
      } catch {
        setHealth(null)
      }
    }
    poll()
    const id = setInterval(poll, 10000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => { fetchManuals() }, [fetchManuals])

  // ── Auto-scroll ───────────────────────────────────────────────────────────

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // ── Toggle manual selection ───────────────────────────────────────────────

  const toggleManual = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  // ── Send query (SSE streaming) ────────────────────────────────────────────

  const handleSend = async (question) => {
    // Add user message
    const userMsgId = Date.now()
    const assistantMsgId = userMsgId + 1

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text: question },
      {
        id: assistantMsgId,
        role: 'assistant',
        streaming: true,
        streamStages: {},
        response: {
          answer: '',
          sources: [],
          question,
          processing_time_ms: 0,
          answer_mode: 'generated',
          is_validated: false,
          pipeline_steps: [],
        },
      },
    ])
    setLoading(true)

    // Helper to update the streaming assistant message
    const updateAssistant = (updater) => {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, ...updater(msg) }
            : msg
        )
      )
    }

    abortRef.current = streamQuery(
      question,
      selectedIds.length > 0 ? selectedIds : null,
      {
        onStage: (data) => {
          updateAssistant(msg => ({
            streamStages: {
              ...msg.streamStages,
              [data.stage]: data,
            },
          }))
        },

        onToken: (data) => {
          updateAssistant(msg => ({
            response: {
              ...msg.response,
              answer: data.replace
                ? data.text
                : msg.response.answer + data.text,
            },
          }))
        },

        onDone: (data) => {
          updateAssistant(msg => ({
            streaming: false,
            streamStages: null,
            response: {
              ...msg.response,
              sources: data.sources || [],
              processing_time_ms: data.processing_time_ms || 0,
              answer_mode: data.answer_mode || 'generated',
              is_validated: data.is_validated || false,
              // Convert streamStages to pipeline_steps for final display
              pipeline_steps: Object.entries(msg.streamStages || {}).map(([name, s]) => ({
                name,
                status: s.status === 'running' ? 'completed' : s.status,
                duration_ms: s.duration_ms || 0,
                detail: s.result || null,
              })),
            },
          }))
          setLoading(false)
        },

        onError: (error) => {
          updateAssistant(msg => ({
            streaming: false,
            streamStages: null,
            response: {
              ...msg.response,
              answer: `⚠️ **Error:** ${error}`,
              answer_mode: 'generated',
            },
          }))
          setLoading(false)
        },
      }
    )
  }

  const hasMessages = messages.length > 0
  const nothingIndexed = manuals.length === 0

  return (
    <div className="flex flex-col h-screen bg-gray-950 overflow-hidden">
      <Header
        health={health}
        hasMessages={hasMessages}
        onClear={() => {
          abortRef.current?.abort()
          setMessages([])
        }}
      />

      <div className="flex flex-1 min-h-0">
        <Sidebar
          manuals={manuals}
          selectedIds={selectedIds}
          onToggle={toggleManual}
          onRefresh={fetchManuals}
          loading={manualsLoading}
        />

        {/* Chat area */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
            {!hasMessages ? (
              <EmptyState />
            ) : (
              messages.map(msg => <Message key={msg.id} msg={msg} />)
            )}
            {loading && !messages.some(m => m.streaming) && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <ChatInput
            onSend={handleSend}
            loading={loading}
            disabled={nothingIndexed}
          />
        </main>
      </div>
    </div>
  )
}
