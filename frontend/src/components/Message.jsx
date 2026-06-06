import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  ChevronDown, ChevronRight, FileText, Clock, User, Bot,
  CheckCircle, AlertTriangle, Zap, Search, Cpu, Shield, BookOpen,
} from 'lucide-react'
import clsx from 'clsx'

// ── Typing indicator ──────────────────────────────────────────────────────────

export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 msg-enter">
      <div className="w-7 h-7 rounded-md bg-blue-500/20 border border-blue-500/30 flex items-center justify-center shrink-0">
        <Bot size={14} className="text-blue-400" />
      </div>
      <div className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-gray-800/60 border border-gray-700/50">
        <div className="typing-dot" />
        <div className="typing-dot" />
        <div className="typing-dot" />
      </div>
    </div>
  )
}

// ── Pipeline stage indicator ─────────────────────────────────────────────────

const STAGE_CONFIG = {
  classify:  { icon: Zap,        label: 'Classifying',  color: 'text-yellow-400' },
  retrieve:  { icon: Search,     label: 'Retrieving',   color: 'text-blue-400' },
  generate:  { icon: Cpu,        label: 'Generating',   color: 'text-purple-400' },
  validate:  { icon: Shield,     label: 'Validating',   color: 'text-green-400' },
  fallback:  { icon: BookOpen,   label: 'Fallback',     color: 'text-orange-400' },
}

export function PipelineStages({ stages }) {
  if (!stages || stages.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5 px-1 mt-1">
      {stages.map((stage, i) => {
        const cfg = STAGE_CONFIG[stage.name] || STAGE_CONFIG.classify
        const Icon = cfg.icon
        const isCompleted = stage.status === 'completed'
        const isSkipped = stage.status === 'skipped'

        return (
          <div
            key={i}
            className={clsx(
              'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border transition-all',
              isSkipped
                ? 'border-gray-700/50 text-gray-600'
                : isCompleted
                  ? 'border-gray-700/50 text-gray-400'
                  : `border-gray-700 ${cfg.color}`
            )}
            title={stage.detail || ''}
          >
            <Icon size={10} />
            <span>{cfg.label}</span>
            {isCompleted && stage.duration_ms > 0 && (
              <span className="text-gray-600 font-mono">{Math.round(stage.duration_ms)}ms</span>
            )}
            {isSkipped && <span className="text-gray-700">—</span>}
          </div>
        )
      })}
    </div>
  )
}

export function StreamingStages({ activeStages }) {
  if (!activeStages || Object.keys(activeStages).length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5 mb-2">
      {Object.entries(activeStages).map(([name, data]) => {
        const cfg = STAGE_CONFIG[name] || STAGE_CONFIG.classify
        const Icon = cfg.icon
        const isRunning = data.status === 'running'

        return (
          <div
            key={name}
            className={clsx(
              'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border',
              isRunning
                ? `${cfg.color} border-current animate-pulse`
                : 'border-gray-700/50 text-gray-500'
            )}
          >
            <Icon size={10} className={isRunning ? 'animate-spin' : ''} />
            <span>{cfg.label}</span>
            {data.duration_ms > 0 && (
              <span className="text-gray-600 font-mono">{Math.round(data.duration_ms)}ms</span>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Source accordion ──────────────────────────────────────────────────────────

function SourceItem({ source }) {
  const [open, setOpen] = useState(false)
  const pct = Math.round(source.relevance_score * 100)
  const rpct = source.reranker_score !== null ? Math.round((Math.max(0, source.reranker_score + 10) / 20) * 100) : null // normalize arbitrary reranker scores roughly to 0-100 for UI

  return (
    <div className="border border-gray-700/50 rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-white/5 transition-colors text-left"
      >
        <FileText size={11} className="text-blue-400 shrink-0" />
        <span className="flex-1 text-gray-300 truncate" title={source.hierarchy_path}>
          {source.hierarchy_path || source.filename}
        </span>
        {source.page && (
          <span className="text-gray-500 shrink-0 font-mono">p.{source.page}</span>
        )}
        <div className="flex gap-1 shrink-0">
          <span className={clsx('px-1.5 py-0.5 rounded text-xs font-mono',
            pct >= 70 ? 'bg-green-500/15 text-green-400' :
            pct >= 40 ? 'bg-yellow-500/15 text-yellow-400' :
            'bg-gray-700 text-gray-500'
          )} title="Hybrid Search Score">
            H:{pct}%
          </span>
          {source.reranker_score !== null && (
            <span className={clsx('px-1.5 py-0.5 rounded text-xs font-mono',
              source.reranker_score > 0 ? 'bg-purple-500/15 text-purple-400' : 'bg-gray-700 text-gray-500'
            )} title={`Reranker Score: ${source.reranker_score}`}>
              R:{source.reranker_score.toFixed(1)}
            </span>
          )}
        </div>
        {open ? <ChevronDown size={11} className="text-gray-500 shrink-0" /> : <ChevronRight size={11} className="text-gray-500 shrink-0" />}
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-gray-700/50">
          <p className="text-xs text-gray-400 leading-relaxed font-mono whitespace-pre-wrap">
            {source.excerpt}
          </p>
        </div>
      )}
    </div>
  )
}

// ── Answer mode badge ────────────────────────────────────────────────────────

function AnswerBadge({ mode, validated }) {
  if (mode === 'direct') {
    return (
      <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full
                        bg-blue-500/10 text-blue-400 border border-blue-500/20">
        <Zap size={9} /> Direct
      </span>
    )
  }
  if (mode === 'extractive_fallback') {
    return (
      <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full
                        bg-orange-500/10 text-orange-400 border border-orange-500/20">
        <AlertTriangle size={9} /> Extractive
      </span>
    )
  }
  if (validated) {
    return (
      <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full
                        bg-green-500/10 text-green-400 border border-green-500/20">
        <CheckCircle size={9} /> Validated
      </span>
    )
  }
  return null
}

// ── Message bubbles ───────────────────────────────────────────────────────────

function UserMessage({ text }) {
  return (
    <div className="flex items-start gap-3 justify-end msg-enter">
      <div className="max-w-[80%] px-3.5 py-2.5 rounded-lg bg-blue-600/20 border border-blue-500/30 text-gray-200 text-sm">
        {text}
      </div>
      <div className="w-7 h-7 rounded-md bg-gray-700 flex items-center justify-center shrink-0">
        <User size={13} className="text-gray-300" />
      </div>
    </div>
  )
}

function AssistantMessage({ response, streaming, streamStages }) {
  const [showSources, setShowSources] = useState(false)
  const hasSources = response.sources?.length > 0

  return (
    <div className="flex items-start gap-3 msg-enter">
      <div className="w-7 h-7 rounded-md bg-blue-500/20 border border-blue-500/30 flex items-center justify-center shrink-0 mt-0.5">
        <Bot size={14} className="text-blue-400" />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {/* Streaming pipeline stages */}
        {streaming && streamStages && <StreamingStages activeStages={streamStages} />}

        {/* Answer */}
        <div className="px-3.5 py-2.5 rounded-lg bg-gray-800/60 border border-gray-700/50">
          <div className="prose prose-invert prose-sm max-w-none text-gray-200 text-sm leading-relaxed">
            <ReactMarkdown>{response.answer}</ReactMarkdown>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 px-1 flex-wrap">
          {hasSources && (
            <button
              onClick={() => setShowSources(v => !v)}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              <FileText size={11} />
              {response.sources.length} source{response.sources.length !== 1 ? 's' : ''}
              {showSources ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
            </button>
          )}
          <AnswerBadge mode={response.answer_mode} validated={response.is_validated} />
          {response.processing_time_ms > 0 && (
            <span className="flex items-center gap-1 text-xs text-gray-600 ml-auto">
              <Clock size={10} />
              {response.processing_time_ms}ms
            </span>
          )}
        </div>

        {/* Pipeline steps (final) */}
        {!streaming && response.pipeline_steps?.length > 0 && (
          <PipelineStages stages={response.pipeline_steps} />
        )}

        {/* Sources */}
        {showSources && hasSources && (
          <div className="space-y-1 pl-1">
            {response.sources.map((s, i) => (
              <SourceItem key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function Message({ msg }) {
  if (msg.role === 'user') return <UserMessage text={msg.text} />
  return (
    <AssistantMessage
      response={msg.response}
      streaming={msg.streaming}
      streamStages={msg.streamStages}
    />
  )
}
