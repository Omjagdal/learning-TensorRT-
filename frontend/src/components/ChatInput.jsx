import React, { useState, useRef, useEffect } from 'react'
import { ArrowUp, Square, Plus, Mic, X, Image as ImageIcon } from 'lucide-react'
import clsx from 'clsx'

export default function ChatInput({ onSend, onStop, loading, disabled }) {
  const [text, setText] = useState('')
  const [attachedImage, setAttachedImage] = useState(null)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  const submit = (e) => {
    if (e) e.preventDefault()
    const q = text.trim()
    if ((!q && !attachedImage) || loading || disabled) return
    onSend(q, attachedImage)
    setText('')
    setAttachedImage(null)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // 5MB limit
    if (file.size > 5 * 1024 * 1024) {
      alert("Image must be smaller than 5MB.")
      e.target.value = ''
      return
    }

    const reader = new FileReader()
    reader.onload = (event) => {
      // Get base64 string without data:image/jpeg;base64, prefix
      const base64String = event.target.result.split(',')[1]
      setAttachedImage(`data:${file.type};base64,${base64String}`)
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="shrink-0 px-4 sm:px-6 pb-6 pt-2 relative z-20">
      <div className="max-w-[768px] mx-auto">
        {/* Input container - completely rounded pill-like shape */}
        <div className="relative flex flex-col w-full rounded-[26px]" style={{ background: '#2f2f2f', padding: '10px 12px' }}>
          
          {/* Image Preview Area */}
          {attachedImage && (
            <div className="relative inline-block mb-2 ml-2 mt-2 w-20 h-20 rounded-xl overflow-hidden border-2 border-[#4a4a4a]">
              <img src={attachedImage} alt="Attached" className="object-cover w-full h-full" />
              <button
                type="button"
                onClick={() => setAttachedImage(null)}
                className="absolute top-1 right-1 bg-black/60 text-white rounded-full p-0.5 hover:bg-black/80 transition-colors"
              >
                <X size={14} />
              </button>
            </div>
          )}

          <form onSubmit={submit} className="flex w-full items-end gap-2">
            
            {/* Hidden File Input */}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileChange}
              disabled={disabled || loading}
            />

            {/* Plus Button (Attachment) */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || loading}
              className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-white/10 transition-colors shrink-0 mb-1 ml-1 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ color: '#ececec' }}
            >
              <Plus size={20} strokeWidth={2} />
            </button>

            {/* Text Area */}
            <textarea
              ref={textareaRef}
              rows={1}
              value={text}
              onChange={e => {
                setText(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
              }}
              onKeyDown={handleKey}
              disabled={disabled || loading}
              placeholder={disabled ? "Index a manual to start..." : "ISRA Vision Chatbot Assistant"}
              className="flex-1 max-h-[200px] py-2 bg-transparent text-[16px] placeholder-[#8e8e8e]
                         resize-none focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed leading-relaxed overflow-y-auto mb-0.5 min-h-[24px]"
              style={{ color: '#ececec' }}
            />

            {/* Send Buttons */}
            <div className="flex items-center gap-1.5 shrink-0 mb-0.5 mr-0.5">

              {loading ? (
                <button
                  type="button"
                  onClick={onStop}
                  className="w-9 h-9 rounded-full flex items-center justify-center transition-all bg-white"
                  title="Stop generating"
                >
                  <Square size={14} className="fill-black text-black" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={submit}
                  disabled={(!text.trim() && !attachedImage) || disabled}
                  className={clsx(
                    "w-9 h-9 rounded-full flex items-center justify-center transition-all",
                    (text.trim() || attachedImage) && !disabled ? "bg-white text-black" : "bg-[#4a4a4a] text-[#2f2f2f]"
                  )}
                  title="Send message"
                >
                  <ArrowUp size={18} strokeWidth={3} />
                </button>
              )}
            </div>
          </form>
        </div>

      </div>
    </div>
  )
}
