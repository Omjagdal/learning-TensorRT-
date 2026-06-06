import React, { useState, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'

const EXAMPLE_QUERIES = [
  'How do I start the machine safely?',
  'What is the maximum operating pressure?',
  'How to reset an overload fault?',
  'What are the lubrication intervals?',
  'Explain the emergency stop procedure',
]

export default function ChatInput({ onSend, loading, disabled }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }, [text])

  const submit = () => {
    const q = text.trim()
    if (!q || loading || disabled) return
    onSend(q)
    setText('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-gray-800 bg-gray-900/50 p-4 space-y-3">
      {/* Example queries */}
      {!loading && (
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLE_QUERIES.slice(0, 3).map(q => (
            <button
              key={q}
              onClick={() => onSend(q)}
              disabled={disabled || loading}
              className="px-2.5 py-1 text-xs rounded-full border border-gray-700 text-gray-500
                         hover:border-blue-500/50 hover:text-gray-300 transition-all
                         disabled:opacity-30 disabled:cursor-not-allowed truncate max-w-xs"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        <div className="flex-1 flex items-end gap-2 px-3 py-2.5 rounded-lg border border-gray-700
                        focus-within:border-blue-500/60 bg-gray-800/50 transition-colors">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={handleKey}
            disabled={disabled || loading}
            placeholder={disabled ? 'No manuals loaded yet…' : 'Ask about your machine…'}
            className="flex-1 resize-none bg-transparent text-sm text-gray-200
                       placeholder-gray-600 focus:outline-none leading-relaxed
                       disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ minHeight: '22px', maxHeight: '160px' }}
          />
        </div>
        <button
          onClick={submit}
          disabled={!text.trim() || loading || disabled}
          className="w-9 h-9 rounded-lg flex items-center justify-center transition-all
                     bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed
                     text-white shrink-0"
        >
          {loading
            ? <Loader2 size={15} className="animate-spin" />
            : <Send size={14} />}
        </button>
      </div>
      <p className="text-xs text-gray-700 text-center">Enter to send · Shift+Enter for new line</p>
    </div>
  )
}
