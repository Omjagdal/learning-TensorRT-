import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  ChevronDown, ChevronRight, ChevronLeft, FileText, Clock, User, Sparkles,
  CheckCircle, AlertTriangle, Zap, Search, Cpu, Shield, BookOpen,
  Layers, Info, Image, X, ZoomIn, ZoomOut, RotateCw, Star, Copy, Check, Code
} from 'lucide-react'
import clsx from 'clsx'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import mermaid from 'mermaid'

// ── Custom ReactMarkdown components ───────────────────────────────────────────

function Mermaid({ chart }) {
  const containerRef = useRef(null)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    let isCancelled = false
    
    const renderChart = async () => {
      if (!chart || !containerRef.current) return
      
      setHasError(false)
      const id = 'mermaid-svg-' + Math.random().toString(36).substring(7)
      
      try {
        mermaid.initialize({ startOnLoad: false, theme: 'dark', suppressErrorRendering: true })
        await mermaid.parse(chart)
        const { svg } = await mermaid.render(id, chart)
        
        if (!isCancelled && containerRef.current) {
          containerRef.current.innerHTML = svg
        }
      } catch (e) {
        if (!isCancelled) {
          setHasError(true)
        }
        // Cleanup orphaned error SVGs injected by mermaid
        const orphaned = document.getElementById(id)
        if (orphaned) orphaned.remove()
        
        const dOrphaned = document.getElementById('d' + id)
        if (dOrphaned) dOrphaned.remove()
      }
    }
    
    renderChart()
    
    return () => {
      isCancelled = true
    }
  }, [chart])

  if (hasError) {
    return (
      <div className="relative my-4 rounded-md overflow-hidden bg-[#0d0d0d] border border-[#2f2f2f] font-sans">
        <div className="flex items-center justify-between px-4 py-2 text-xs text-gray-300 bg-[#2f2f2f]">
          <span className="font-mono text-gray-200">mermaid (typing...)</span>
        </div>
        <div className="overflow-x-auto text-[14px]">
          <SyntaxHighlighter
            style={vscDarkPlus}
            language="markdown"
            PreTag="div"
            customStyle={{ margin: 0, padding: '1rem', background: 'transparent' }}
            codeTagProps={{ style: { fontFamily: '"JetBrains Mono", monospace' } }}
          >
            {chart}
          </SyntaxHighlighter>
        </div>
      </div>
    )
  }

  return <div ref={containerRef} className="mermaid-diagram overflow-x-auto p-4 flex justify-center bg-[#0d0d0d] rounded-md my-4 border border-[#2f2f2f]" />
}

function CodeBlock({ node, inline, className, children, ...props }) {
  const [copied, setCopied] = useState(false)
  const match = /language-(\w+)/.exec(className || '')
  const lang = match ? match[1] : 'text'

  const handleCopy = () => {
    navigator.clipboard.writeText(String(children).replace(/\n$/, ''))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!inline && lang === 'mermaid') {
    return <Mermaid chart={String(children).replace(/\n$/, '')} />
  }

  if (!inline) {
    return (
      <div className="relative my-4 rounded-md overflow-hidden bg-[#0d0d0d] border border-[#2f2f2f] font-sans">
        <div className="flex items-center justify-between px-4 py-2 text-xs text-gray-300 bg-[#2f2f2f]">
          <span className="font-mono text-gray-200">{lang}</span>
          <button 
            onClick={handleCopy} 
            className="flex items-center gap-1.5 hover:text-white transition-colors"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? 'Copied!' : 'Copy code'}</span>
          </button>
        </div>
        <div className="overflow-x-auto text-[14px]">
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={lang}
            PreTag="div"
            customStyle={{ margin: 0, padding: '1rem', background: 'transparent' }}
            codeTagProps={{ style: { fontFamily: '"JetBrains Mono", monospace' } }}
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        </div>
      </div>
    )
  }

  return (
    <code className={clsx(className, 'text-emerald-400 px-1.5 py-0.5 rounded-md text-[14px] font-mono')}
      style={{ background: 'var(--bg-tertiary)' }} {...props}>
      {children}
    </code>
  )
}

const markdownComponents = {
  code: CodeBlock,
  table: ({ node, ...props }) => (
    <div className="my-6 rounded-lg border border-[var(--border)]">
      <table className="w-full text-left border-collapse text-[15px]" {...props} />
    </div>
  ),
  thead: ({ node, ...props }) => (
    <thead className="bg-[var(--bg-tertiary)] border-b border-[var(--border)]" {...props} />
  ),
  th: ({ node, ...props }) => (
    <th className="px-4 py-3 font-semibold text-[var(--text-primary)]" {...props} />
  ),
  td: ({ node, ...props }) => (
    <td className="px-4 py-3 border-b border-[var(--border)] text-[var(--text-secondary)] last:border-0" {...props} />
  ),
}

// ── Typing indicator ──────────────────────────────────────────────────────────

export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 msg-enter">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <Sparkles size={14} className="text-emerald-400" />
      </div>
      <div className="flex items-center gap-1.5 px-4 py-3 rounded-xl"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="typing-dot" />
        <div className="typing-dot" />
        <div className="typing-dot" />
      </div>
    </div>
  )
}

// ── Pipeline stage indicator ─────────────────────────────────────────────────

const STAGE_CONFIG = {
  classify:  { icon: Zap,        label: 'Classifying',  color: 'text-amber-400' },
  retrieve:  { icon: Search,     label: 'Retrieving',   color: 'text-blue-400' },
  rerank:    { icon: Search,     label: 'Reranking',    color: 'text-cyan-400' },
  generate:  { icon: Cpu,        label: 'Generating',   color: 'text-purple-400' },
  validate:  { icon: Shield,     label: 'Validating',   color: 'text-emerald-400' },
  fallback:  { icon: BookOpen,   label: 'Fallback',     color: 'text-orange-400' },
}

// ── Premium streaming indicator ──────────────────────────────────────────────

export function StreamingIndicator() {
  return (
    <div className="flex items-center gap-3 mb-3">
      <div className="flex items-center pt-1 pb-2">
        <div className="bouncy-dot" />
        <div className="bouncy-dot" />
        <div className="bouncy-dot" />
      </div>
      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>Thinking…</span>
    </div>
  )
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ score, maxScore = 1, color = 'bg-blue-500' }) {
  const pct = Math.min((score / maxScore) * 100, 100)
  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="flex-1 h-1 rounded-full bg-[var(--border)] overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all duration-500', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ── Source accordion ──────────────────────────────────────────────────────────

function SourceItem({ source, index }) {
  const [open, setOpen] = useState(false)
  const score = source.relevance_score
  const scoreLabel = score >= 1 ? Math.round(score) : score.toFixed(3)

  return (
    <div className="border border-[var(--border)] rounded-xl overflow-hidden source-item-enter bg-[var(--bg-secondary)]"
         style={{ animationDelay: `${index * 50}ms` }}>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-xs hover:bg-[var(--bg-hover)] transition-colors text-left"
      >
        <FileText size={12} className="text-blue-400 shrink-0" />
        <span className="flex-1 text-[var(--text-secondary)] font-medium truncate" title={source.hierarchy_path}>
          {source.hierarchy_path || source.filename}
        </span>
        {source.page && (
          <span className="text-[#555] shrink-0 font-mono">p.{source.page}</span>
        )}
        {source.has_images && (
          <span className="shrink-0">
            <Image size={11} className="text-teal-400" />
          </span>
        )}
        <div className="flex gap-1 shrink-0">
          <span className={clsx('px-1.5 py-0.5 rounded-md text-[11px] font-mono font-medium',
            score >= 0.5 ? 'bg-emerald-500/10 text-emerald-400' :
            score >= 0.02 ? 'bg-yellow-500/10 text-yellow-400' :
            'bg-[var(--bg-card)] text-[var(--text-muted)]'
          )} title={`Search Score: ${score}`}>
            {scoreLabel}
          </span>
          {source.reranker_score != null && (
            <span className={clsx('px-1.5 py-0.5 rounded-md text-[11px] font-mono font-medium',
              source.reranker_score > 0 ? 'bg-purple-500/10 text-purple-400' : 'bg-[var(--bg-card)] text-[var(--text-muted)]'
            )} title={`Reranker Score: ${source.reranker_score}`}>
              R:{source.reranker_score.toFixed(1)}
            </span>
          )}
        </div>
        {open ? <ChevronDown size={12} className="text-[#555] shrink-0" /> : <ChevronRight size={12} className="text-[#555] shrink-0" />}
      </button>
      {open && (
        <div className="px-3 pb-3 pt-2 border-t border-[var(--border)] space-y-2">
          <div className="flex items-center gap-3 text-xs">
            <span className="text-[var(--text-muted)] w-16 shrink-0">Relevance</span>
            <ScoreBar score={score} maxScore={score >= 0.1 ? 1 : 0.05} color="bg-blue-500" />
            <span className="text-[var(--text-muted)] font-mono w-12 text-right">{scoreLabel}</span>
          </div>
          {source.reranker_score != null && (
            <div className="flex items-center gap-3 text-xs">
              <span className="text-[var(--text-muted)] w-16 shrink-0">Reranker</span>
              <ScoreBar
                score={Math.max(0, source.reranker_score + 5)}
                maxScore={10}
                color="bg-purple-500"
              />
              <span className="text-[var(--text-muted)] font-mono w-12 text-right">{source.reranker_score.toFixed(2)}</span>
            </div>
          )}
          <div className="mt-2">
            <p className="text-[11px] text-[var(--text-muted)] mb-1 flex items-center gap-1 font-medium">
              <Info size={10} /> Knowledge excerpt:
            </p>
            <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed font-mono whitespace-pre-wrap
                          bg-[var(--bg-primary)] rounded-lg p-3 border border-[var(--border)]">
              {source.excerpt}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Diagram Lightbox ─────────────────────────────────────────────────────────

export function DiagramLightbox({ images, currentIndex, onChangeIndex, onClose }) {
  const [zoom, setZoom] = useState(1)
  const image = images[currentIndex]

  useEffect(() => {
    setZoom(1)
  }, [currentIndex])

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.25, 3))
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.25, 0.5))
  const handleReset = () => setZoom(1)

  const handlePrev = useCallback((e) => {
    if (e) e.stopPropagation()
    onChangeIndex(currentIndex > 0 ? currentIndex - 1 : images.length - 1)
  }, [currentIndex, images.length, onChangeIndex])

  const handleNext = useCallback((e) => {
    if (e) e.stopPropagation()
    onChangeIndex(currentIndex < images.length - 1 ? currentIndex + 1 : 0)
  }, [currentIndex, images.length, onChangeIndex])

  const handleWheel = useCallback((e) => {
    // Use wheel delta to zoom in or out
    const zoomIntensity = 0.005;
    const delta = e.deltaY;
    setZoom(z => {
      const newZoom = z - delta * zoomIntensity;
      return Math.max(0.2, Math.min(newZoom, 5));
    });
  }, []);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft') handlePrev()
      else if (e.key === 'ArrowRight') handleNext()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose, handlePrev, handleNext])

  return (
    <div className="diagram-lightbox-overlay" onClick={onClose}>
      <div className="diagram-lightbox-content" onClick={e => e.stopPropagation()}>
        {/* Lightbox header */}
        <div className="diagram-lightbox-header">
          <span className="text-[13px] font-medium" style={{ color: 'var(--text-secondary)' }}>
            📄 Page {image.page} — {image.hierarchy} ({currentIndex + 1} / {images.length})
          </span>
          <div className="flex items-center gap-1">
            <button onClick={handleZoomOut} className="diagram-lightbox-btn" title="Zoom out">
              <ZoomOut size={14} />
            </button>
            <span className="text-[11px] font-mono px-2" style={{ color: 'var(--text-muted)' }}>
              {Math.round(zoom * 100)}%
            </span>
            <button onClick={handleZoomIn} className="diagram-lightbox-btn" title="Zoom in">
              <ZoomIn size={14} />
            </button>
            <button onClick={handleReset} className="diagram-lightbox-btn" title="Reset zoom">
              <RotateCw size={14} />
            </button>
            <button onClick={onClose} className="diagram-lightbox-btn diagram-lightbox-close" title="Close">
              <X size={16} />
            </button>
          </div>
        </div>
        {/* Image container */}
        <div className="diagram-lightbox-body relative" onWheel={handleWheel}>
          {images.length > 1 && (
            <button onClick={handlePrev} className="absolute left-4 p-2 bg-black/50 text-white rounded-full hover:bg-black/80 transition-colors z-10" title="Previous (Left Arrow)">
              <ChevronLeft size={24} />
            </button>
          )}
          <img
            src={image.url}
            alt={`Manual diagram — Page ${image.page}`}
            style={{ transform: `scale(${zoom})`, transformOrigin: 'center center', transition: 'transform 0.05s ease-out' }}
            className="diagram-lightbox-img"
          />
          {images.length > 1 && (
            <button onClick={handleNext} className="absolute right-4 p-2 bg-black/50 text-white rounded-full hover:bg-black/80 transition-colors z-10" title="Next (Right Arrow)">
              <ChevronRight size={24} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Diagrams section ─────────────────────────────────────────────────────────

function DiagramsSection({ images, onOpenFolderView }) {
  const [lightboxData, setLightboxData] = useState(null)

  if (!images || images.length === 0) return null

  // Collect unique thumbnails
  const mainThumbnails = []
  const seen = new Set()
  
  for (const img of images) {
    if (img.image_url) {
      if (!seen.has(img.image_url)) {
        seen.add(img.image_url)
        mainThumbnails.push(img)
      }
    }
  }

  if (mainThumbnails.length === 0) return null
  
  const handleOpenFolder = (mainImg) => {
    let gallery = []
    
    // Add adjacent images
    if (mainImg.adjacent_images && mainImg.adjacent_images.length > 0) {
      mainImg.adjacent_images.forEach(a => {
        gallery.push({ url: a.image_url, page: a.page, hierarchy: a.hierarchy_path })
      })
    }
    
    // Add main image
    gallery.push({ url: mainImg.image_url, page: mainImg.page, hierarchy: mainImg.hierarchy_path || mainImg.filename })
    
    // Sort by page
    gallery.sort((a, b) => a.page - b.page)
    
    // Trigger callback to switch view in App.jsx
    if (onOpenFolderView) {
      onOpenFolderView({ gallery, title: mainImg.hierarchy_path || mainImg.filename })
    }
  }

  const handleOpenLightbox = (mainImg, targetUrl) => {
    let gallery = []
    
    // Add adjacent images
    if (mainImg.adjacent_images && mainImg.adjacent_images.length > 0) {
      mainImg.adjacent_images.forEach(a => {
        gallery.push({ url: a.image_url, page: a.page, hierarchy: a.hierarchy_path })
      })
    }
    
    // Add main image
    gallery.push({ url: mainImg.image_url, page: mainImg.page, hierarchy: mainImg.hierarchy_path || mainImg.filename })
    
    // Sort by page
    gallery.sort((a, b) => a.page - b.page)
    
    // Find the starting index (the clicked image)
    const startIndex = gallery.findIndex(g => g.url === (targetUrl || mainImg.image_url))
    
    setLightboxData({
       gallery,
       startIndex: Math.max(0, startIndex)
    })
  }

  return (
    <>
      <div className="diagram-grid pt-2 pb-4">
        {mainThumbnails.map((img, i) => {
          const hasAdjacent = img.adjacent_images && img.adjacent_images.length > 0;
          
          return (
            <div key={img.image_url} className="diagram-folder-container">
              {/* Main Thumbnail (Folder) */}
              <div
                className="diagram-thumbnail-card"
                style={{ animationDelay: `${i * 60}ms` }}
                onClick={() => hasAdjacent ? handleOpenFolder(img) : handleOpenLightbox(img)}
              >
            <div className="diagram-thumbnail-wrapper">
              <img
                src={img.image_url}
                alt={`Diagram — Page ${img.page}`}
                className="diagram-thumbnail-img"
                loading="lazy"
              />
              <div className="diagram-thumbnail-overlay">
                <ZoomIn size={18} className="text-white" />
              </div>
              {/* Badge */}
              {hasAdjacent && (
                <div className="absolute top-2 right-2 bg-blue-500 text-white text-[10px] font-bold px-2 py-1 rounded shadow-lg flex items-center gap-1">
                  <Layers size={10} />
                  {img.adjacent_images.length + 1}
                </div>
              )}
            </div>
            <div className="diagram-thumbnail-label">
              <span className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
                p.{img.page}
              </span>
              <span className="text-[10px] truncate flex-1" style={{ color: 'var(--text-muted)' }} title={img.hierarchy_path}>
                {(img.hierarchy_path || img.filename).split(' > ').pop()}
              </span>
              {hasAdjacent && (
                <ChevronRight size={14} className="text-[var(--text-muted)]" />
              )}
            </div>
          </div>
        </div>
        )})}
      </div>

      {lightboxData !== null && (
        <DiagramLightbox
          images={lightboxData.gallery}
          currentIndex={lightboxData.startIndex}
          onChangeIndex={(idx) => setLightboxData({ ...lightboxData, startIndex: idx })}
          onClose={() => setLightboxData(null)}
        />
      )}
    </>
  )
}

// ── Answer mode badge ────────────────────────────────────────────────────────

function AnswerBadge({ mode, validated }) {
  if (mode === 'direct') {
    return (
      <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
        <Zap size={10} /> Direct
      </span>
    )
  }
  if (mode === 'extractive_fallback') {
    return (
      <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20">
        <AlertTriangle size={10} /> Extractive
      </span>
    )
  }
  if (validated) {
    return (
      <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <CheckCircle size={10} /> Validated
      </span>
    )
  }
  return null
}

// ── Message bubbles ───────────────────────────────────────────────────────────

function UserMessage({ text, image }) {
  return (
    <div className="flex items-start gap-3 justify-end msg-enter">
      <div className="max-w-[75%] flex flex-col items-end gap-2">
        {image && (
          <div className="rounded-2xl rounded-tr-md overflow-hidden border border-[var(--border)] max-w-sm">
            <img src={image} alt="User Uploaded" className="w-full h-auto object-cover" />
          </div>
        )}
        {text && (
          <div className="px-4 py-3 rounded-2xl rounded-tr-md text-[17px] leading-relaxed"
            style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}>
            {text}
          </div>
        )}
      </div>
      <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-[11px] font-semibold"
        style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
        Y
      </div>
    </div>
  )
}

function AssistantMessage({ response, streaming, streamStages, bookmarks, onToggleBookmark, onOpenFolderView }) {
  const [showSources, setShowSources] = useState(false)
  const hasSources = response.sources?.length > 0
  const isBookmarked = bookmarks.some(b => b.question === response.question)

  return (
    <div className="flex items-start gap-3 msg-enter">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <Sparkles size={14} className="text-emerald-400" />
      </div>
      <div className="flex-1 min-w-0 space-y-2 max-w-[85%]">
        {streaming && <StreamingIndicator />}

        {/* Retrieved Images (Diagrams) */}
        {/* Diagrams / Images */}
        <DiagramsSection images={response.images} onOpenFolderView={onOpenFolderView} />

        {/* Answer */}
        <div className="text-[17px] leading-[1.85]" style={{ color: 'var(--text-primary)' }}>
          <div className="prose prose-lg max-w-none
                          prose-p:mb-5 prose-p:mt-2
                          prose-ul:my-5 prose-ol:my-5
                          prose-li:my-3
                          prose-headings:font-semibold prose-headings:mt-7 prose-headings:mb-4
                          prose-code:text-emerald-400 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:text-[15px]
                          prose-pre:rounded-xl prose-pre:my-5
                          prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline"
            style={{ '--tw-prose-body': 'var(--text-primary)', '--tw-prose-headings': 'var(--text-primary)', '--tw-prose-bold': 'var(--text-primary)', '--tw-prose-bullets': 'var(--text-muted)', '--tw-prose-counters': 'var(--text-muted)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{response.answer}</ReactMarkdown>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 flex-wrap">
          {hasSources && (
            <button
              onClick={() => setShowSources(v => !v)}
              className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
            >
              <Layers size={11} />
              <span>
                {response.sources.length} source{response.sources.length !== 1 ? 's' : ''}
              </span>
              {showSources ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
            </button>
          )}


          <AnswerBadge mode={response.answer_mode} validated={response.is_validated} />
          
          {/* Bookmark Button */}
          {!streaming && (
            <button
              onClick={() => onToggleBookmark(response)}
              className="ml-2 flex items-center justify-center p-1.5 rounded-md hover:bg-[var(--bg-hover)] transition-colors group"
              title={isBookmarked ? "Remove Bookmark" : "Bookmark this answer"}
            >
              <Star 
                size={14} 
                className={clsx(
                  "transition-colors",
                  isBookmarked 
                    ? "fill-yellow-400 text-yellow-400" 
                    : "text-[var(--text-muted)] group-hover:text-yellow-400"
                )} 
              />
            </button>
          )}

          {response.processing_time_ms > 0 && (
            <span className="flex items-center gap-1 text-[11px] text-[var(--text-muted)] ml-auto font-mono">
              <Clock size={10} />
              {response.processing_time_ms}ms
            </span>
          )}
        </div>



        {/* Sources */}
        {showSources && hasSources && (
          <div className="space-y-1.5 pt-2">
            <div className="flex items-center gap-1.5 mb-2 text-[11px] font-medium text-[var(--text-muted)]">
              <Info size={10} />
              <span>Documents used for this answer:</span>
            </div>
            {response.sources.map((s, i) => (
              <SourceItem key={i} source={s} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function Message({ msg, bookmarks, onToggleBookmark, onOpenFolderView }) {
  if (msg.role === 'user') return <UserMessage text={msg.text} image={msg.image} />
  return (
    <AssistantMessage
      response={msg.response}
      streaming={msg.streaming}
      streamStages={msg.streamStages}
      bookmarks={bookmarks}
      onToggleBookmark={onToggleBookmark}
      onOpenFolderView={onOpenFolderView}
    />
  )
}
