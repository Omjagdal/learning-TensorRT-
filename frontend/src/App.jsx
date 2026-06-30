import React, { useState, useEffect, useRef, useCallback } from 'react'
import { listManuals, deleteManual, streamQuery, getHealth, getKnowledgeBase } from './utils/api'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatInput from './components/ChatInput'
import { Message, TypingIndicator } from './components/Message'
import KnowledgeInfo from './components/KnowledgeInfo'
import FolderView from './components/FolderView'

const SUGGESTION_PROMPTS = [
  'Explain me the SOP(standard operating procedure) diagram & its steps',
  "What are the Do's and Don'ts?",
  'Explain vision teaching and parametrization steps.',
  'What are the limits for bead width?',
  'How does the image recording sequence work?',
  'Describe the control architecture of quiss vision2d .',
  'What are the electrical connections with diagram?',
  'Provide hardware information about sensors and cables diagram.'
]

function EmptyState({ onSend, disabled }) {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center px-8 pb-4">
      {/* Green gradient orb */}
      <div className="green-orb mb-10" />

      {/* Greeting */}
      <h2 className="text-[32px] md:text-[40px] font-semibold leading-tight tracking-tight mb-2" style={{ color: 'var(--text-primary)' }}>
        {greeting}
      </h2>
      <h3 className="text-[32px] md:text-[40px] font-semibold leading-tight tracking-tight mb-4" style={{ color: 'var(--text-secondary)' }}>
        Can I help you with anything?
      </h3>
      <p className="text-[14px] max-w-md mb-10 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
        Choose a prompt below or write your own to start<br />
        chatting with ISRA Vision Chatbot Assistant
      </p>

      {/* Suggestion cards */}
      <div className="flex flex-wrap justify-center gap-3 max-w-3xl">
        {SUGGESTION_PROMPTS.map(q => (
          <button
            key={q}
            onClick={() => onSend(q)}
            disabled={disabled}
            className="suggestion-card"
          >
            {q}
          </button>
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
  const [showKnowledge, setShowKnowledge] = useState(false)
  const [knowledgeData, setKnowledgeData] = useState(null)
  const [theme, setTheme] = useState('dark')
  const [folderViewData, setFolderViewData] = useState(null)

  // Bookmarks state from localStorage
  const [bookmarks, setBookmarks] = useState(() => {
    try {
      const saved = localStorage.getItem('manualmind_bookmarks')
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  // Save bookmarks to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('manualmind_bookmarks', JSON.stringify(bookmarks))
  }, [bookmarks])

  const toggleBookmark = (response) => {
    setBookmarks(prev => {
      const exists = prev.find(b => b.question === response.question)
      if (exists) {
        return prev.filter(b => b.question !== response.question)
      } else {
        return [...prev, {
          id: Date.now(),
          question: response.question,
          answer: response.answer,
          sources: response.sources,
          images: response.images,
          timestamp: Date.now()
        }]
      }
    })
  }

  const handleSelectBookmark = (bookmark) => {
    // Add both user message and assistant message instantly
    const userMsgId = Date.now()
    const assistantMsgId = userMsgId + 1

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text: bookmark.question },
      {
        id: assistantMsgId,
        role: 'assistant',
        streaming: false,
        response: {
          answer: bookmark.answer,
          sources: bookmark.sources || [],
          images: bookmark.images || [],
          question: bookmark.question,
          processing_time_ms: 0,
          answer_mode: 'bookmarked',
          is_validated: true,
          pipeline_steps: []
        }
      }
    ])
  }

  const bottomRef = useRef(null)
  const abortRef = useRef(null)
  const autoScrollEnabled = useRef(true)

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark')

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
    if (autoScrollEnabled.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'instant' })
    }
  }, [messages, loading])

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target
    // If user is within 100px of the bottom, keep auto-scrolling
    const isAtBottom = scrollHeight - scrollTop <= clientHeight + 100
    autoScrollEnabled.current = isAtBottom
  }

  // ── Toggle manual selection ───────────────────────────────────────────────

  const toggleManual = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleDeleteManual = async (manualId) => {
    try {
      await deleteManual(manualId)
      setSelectedIds(prev => prev.filter(id => id !== manualId))
      fetchManuals()
    } catch (err) {
      alert(`Delete failed: ${err.response?.data?.detail || err.message}`)
    }
  }

  // ── Knowledge Base Info ───────────────────────────────────────────────────

  const handleShowKnowledge = async () => {
    setShowKnowledge(true)
    try {
      const res = await getKnowledgeBase()
      setKnowledgeData(res.data)
    } catch {
      // If API fails, show what we can
      setKnowledgeData(null)
    }
  }

  // ── Send query (SSE streaming) ────────────────────────────────────────────

  const handleSend = async (question, imageBase64 = null) => {
    // Add user message
    const userMsgId = Date.now()
    const assistantMsgId = userMsgId + 1

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text: question, image: imageBase64 },
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
      imageBase64,
      {
        onStage: (data) => {
          updateAssistant(msg => ({
            streamStages: {
              ...msg.streamStages,
              [data.stage]: data,
            },
          }))
        },

        onImages: (data) => {
          updateAssistant(msg => ({
            response: {
              ...msg.response,
              images: data,
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
              images: data.images || [],
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

  const handleStop = () => {
    abortRef.current?.abort()
    setLoading(false)
    setMessages(prev => prev.map(msg =>
      msg.streaming
        ? {
          ...msg,
          streaming: false,
          streamStages: null,
          response: {
            ...msg.response,
            answer: msg.response.answer ? msg.response.answer + '\n\n*(Stopped by user)*' : '*(Stopped by user)*'
          }
        }
        : msg
    ))
  }

  const hasMessages = messages.length > 0
  const nothingIndexed = manuals.length === 0

  return (
    <div className={`flex flex-col h-screen overflow-hidden ${theme === 'light' ? 'light' : ''}`} style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      <Header
        health={health}
        hasMessages={hasMessages}
        onClear={() => {
          abortRef.current?.abort()
          setMessages([])
        }}
        onShowKnowledge={handleShowKnowledge}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <div className="flex flex-1 min-h-0">
        <Sidebar
          manuals={manuals}
          selectedIds={selectedIds}
          onToggle={toggleManual}
          onRefresh={fetchManuals}
          onDelete={handleDeleteManual}
          loading={manualsLoading}
          bookmarks={bookmarks}
          onSelectBookmark={handleSelectBookmark}
          onRemoveBookmark={(bookmark) => toggleBookmark({ question: bookmark.question })}
        />

        {/* Chat area */}
        <main className="flex-1 flex flex-col min-w-0">
          {folderViewData ? (
            <FolderView
              data={folderViewData}
              onBack={() => setFolderViewData(null)}
            />
          ) : (
            <>
              {/* Messages */}
              <div
                className="flex-1 overflow-y-auto px-6 py-5 space-y-6"
                onScroll={handleScroll}
              >
                {!hasMessages ? (
                  <EmptyState onSend={handleSend} disabled={nothingIndexed} />
                ) : (
                  <div className="max-w-3xl mx-auto space-y-6">
                    {messages.map(msg => (
                      <Message
                        key={msg.id}
                        msg={msg}
                        bookmarks={bookmarks}
                        onToggleBookmark={toggleBookmark}
                        onOpenFolderView={setFolderViewData}
                      />
                    ))}
                  </div>
                )}
                {loading && !messages.some(m => m.streaming) && (
                  <div className="max-w-3xl mx-auto">
                    <TypingIndicator />
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              {/* Input */}
              <ChatInput
                onSend={handleSend}
                onStop={handleStop}
                loading={loading}
                disabled={nothingIndexed}
              />
            </>
          )}
        </main>
      </div>

      {/* Knowledge Info Modal */}
      {showKnowledge && (
        <KnowledgeInfo
          data={knowledgeData}
          onClose={() => setShowKnowledge(false)}
        />
      )}
    </div>
  )
}
