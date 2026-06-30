import React, { useState } from 'react'
import {
  X, Database, Brain, Cpu, Search, Shield, Zap, BookOpen,
  FileText, Layers, Settings, Activity, HardDrive, CheckCircle,
  AlertCircle, Loader2, ChevronDown, ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'

// ── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const config = {
    loaded: { icon: CheckCircle, label: 'Loaded', color: 'text-green-400 bg-green-500/10 border-green-500/20' },
    loading: { icon: Loader2, label: 'Loading', color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
    unavailable: { icon: AlertCircle, label: 'Unavailable', color: 'text-red-400 bg-red-500/10 border-red-500/20' },
  }
  const cfg = config[status] || config.unavailable
  const Icon = cfg.icon

  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border', cfg.color)}>
      <Icon size={10} className="" />
      {cfg.label}
    </span>
  )
}

// ── Model type icon ──────────────────────────────────────────────────────────

function ModelTypeIcon({ type }) {
  const icons = {
    embedding: <Layers size={16} className="text-blue-400" />,
    llm: <Brain size={16} className="text-purple-400" />,
    reranker: <Search size={16} className="text-cyan-400" />,
  }
  return icons[type] || <Cpu size={16} className="text-gray-400" />
}

// ── Manual card ──────────────────────────────────────────────────────────────

function ManualCard({ manual }) {
  return (
    <div className="ki-manual-card group" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
             style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)' }}>
          <FileText size={18} className="text-blue-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{manual.filename}</p>
          {manual.manual_name && (
            <p className="text-xs truncate mt-0.5" style={{ color: 'var(--text-secondary)' }}>{manual.manual_name}</p>
          )}
          <div className="flex items-center gap-3 mt-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1">
              <BookOpen size={10} /> {manual.page_count} pages
            </span>
            <span className="flex items-center gap-1">
              <Layers size={10} /> {manual.chunk_count} chunks
            </span>
            <span>{manual.size_mb} MB</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Model card ───────────────────────────────────────────────────────────────

function ModelCard({ model }) {
  return (
    <div className="ki-model-card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div className="flex items-center gap-3 mb-2">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center"
             style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)' }}>
          <ModelTypeIcon type={model.model_type} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{model.name}</p>
            <StatusBadge status={model.status} />
          </div>
          <p className="text-xs capitalize" style={{ color: 'var(--text-muted)' }}>{model.model_type} · {model.provider}</p>
        </div>
      </div>
      {model.details && (
        <p className="text-xs pl-12" style={{ color: 'var(--text-secondary)' }}>{model.details}</p>
      )}
    </div>
  )
}

// ── Pipeline visualization ──────────────────────────────────────────────────

function PipelineViz({ pipeline }) {
  const stages = [
    {
      icon: Zap, label: 'Classify', color: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/5',
      active: pipeline.classify_enabled,
      detail: 'Query intent detection',
    },
    {
      icon: Search, label: 'Retrieve', color: 'text-blue-400 border-blue-500/30 bg-blue-500/5',
      active: true,
      detail: `Top ${pipeline.retrieval_top_k} · ${pipeline.bm25_enabled ? 'Hybrid (Vector + BM25)' : 'Vector only'}`,
    },
    {
      icon: Layers, label: 'Rerank', color: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/5',
      active: pipeline.reranker_enabled,
      detail: `Top ${pipeline.reranker_top_k} from candidates`,
    },
    {
      icon: Cpu, label: 'Generate', color: 'text-purple-400 border-purple-500/30 bg-purple-500/5',
      active: true,
      detail: 'LLM answer generation',
    },
    {
      icon: Shield, label: 'Validate', color: 'text-green-400 border-green-500/30 bg-green-500/5',
      active: pipeline.validation_enabled,
      detail: 'Grounding verification',
    },
  ]

  return (
    <div className="ki-pipeline flex flex-wrap gap-2">
      {stages.map((stage, i) => {
        const Icon = stage.icon
        return (
          <div key={stage.label} className="flex items-center">
            <div className={clsx(
              'flex items-center gap-2 px-3 py-2 rounded-lg border transition-all',
              stage.active ? stage.color : ''
            )} style={!stage.active ? { background: 'var(--bg-tertiary)', borderColor: 'var(--border)', color: 'var(--text-muted)' } : {}}>
              <Icon size={14} />
              <div>
                <p className="text-xs font-medium" style={!stage.active ? {} : { color: 'var(--text-primary)' }}>{stage.label}</p>
                <p className="text-[10px]" style={!stage.active ? {} : { color: 'var(--text-secondary)' }}>{stage.detail}</p>
              </div>
              {!stage.active && (
                <span className="text-[10px] ml-1 opacity-50">OFF</span>
              )}
            </div>
            {i < stages.length - 1 && (
              <div className="w-5 h-[1px] mx-0.5 shrink-0 hidden sm:block" style={{ background: 'var(--border)' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Config details ──────────────────────────────────────────────────────────

function ConfigSection({ pipeline, data }) {
  const [open, setOpen] = useState(false)

  const items = [
    { label: 'Chunk Size', value: `${pipeline.chunk_size} tokens` },
    { label: 'Chunk Overlap', value: `${pipeline.chunk_overlap} tokens` },
    { label: 'Retrieval Top-K', value: pipeline.retrieval_top_k },
    { label: 'Reranker Top-K', value: pipeline.reranker_top_k },
    { label: 'Hybrid Alpha', value: `${pipeline.hybrid_search_alpha} (vector weight)` },
    { label: 'Relevance Threshold', value: pipeline.relevance_threshold },
    { label: 'Vector DB', value: data.vector_db === 'qdrant-embedded' ? 'Qdrant (Embedded)' : 'Qdrant (Remote)' },
    { label: 'Embedding Dim', value: `${data.embedding_dimension}d` },
    { label: 'Search Method', value: data.search_method.charAt(0).toUpperCase() + data.search_method.slice(1) },
  ]

  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-sm transition-colors w-full"
        style={{ color: 'var(--text-muted)' }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
      >
        <Settings size={14} />
        <span className="font-medium">Pipeline Configuration</span>
        {open ? <ChevronDown size={12} className="ml-auto" /> : <ChevronRight size={12} className="ml-auto" />}
      </button>
      {open && (
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {items.map(item => (
            <div key={item.label} className="flex justify-between items-center px-3 py-2 rounded-md"
                 style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)' }}>
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
              <span className="text-xs font-mono" style={{ color: 'var(--text-primary)' }}>{item.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Stats bar ───────────────────────────────────────────────────────────────

function StatsBar({ data }) {
  const stats = [
    { icon: BookOpen, label: 'Manuals', value: data.total_manuals, color: 'text-blue-400' },
    { icon: Layers, label: 'Chunks', value: data.total_chunks.toLocaleString(), color: 'text-purple-400' },
    { icon: Database, label: 'Vectors', value: data.total_vectors.toLocaleString(), color: 'text-cyan-400' },
  ]

  return (
    <div className="grid grid-cols-3 gap-3">
      {stats.map(stat => {
        const Icon = stat.icon
        return (
          <div key={stat.label} className="ki-stat-card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <Icon size={18} className={stat.color} />
            <div>
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{stat.value}</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Main modal ──────────────────────────────────────────────────────────────

export default function KnowledgeInfo({ data, onClose }) {
  if (!data) return null

  return (
    <div className="ki-overlay" onClick={onClose} style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="ki-modal" onClick={e => e.stopPropagation()} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center"
                 style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)' }}>
              <Database size={18} className="text-blue-400" />
            </div>
            <div>
              <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>Knowledge Base</h2>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Information sources powering AI responses
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {data.offline_mode && (
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs"
                    style={{ background: 'var(--bg-tertiary)', color: 'var(--accent-green)', border: '1px solid var(--border)' }}>
                <HardDrive size={10} /> Offline
              </span>
            )}
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
              style={{ color: 'var(--text-muted)' }}
              onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-6 overflow-y-auto max-h-[calc(80vh-70px)]">
          {/* Stats overview */}
          <StatsBar data={data} />

          {/* Indexed Manuals */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <BookOpen size={14} className="text-blue-400" />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Indexed Documents
              </h3>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                (The LLM generates answers from these)
              </span>
            </div>
            {data.manuals.length === 0 ? (
              <div className="text-center py-6 text-sm border border-dashed rounded-lg"
                   style={{ color: 'var(--text-muted)', borderColor: 'var(--border)' }}>
                No documents indexed yet.
              </div>
            ) : (
              <div className="space-y-2">
                {data.manuals.map(m => (
                  <ManualCard key={m.manual_id} manual={m} />
                ))}
              </div>
            )}
          </div>

          {/* AI Models */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Brain size={14} className="text-purple-400" />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>AI Models</h3>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                (Models that process and understand your queries)
              </span>
            </div>
            <div className="space-y-2">
              {data.models.map((m, i) => (
                <ModelCard key={i} model={m} />
              ))}
            </div>
          </div>

          {/* Self-RAG Pipeline */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Activity size={14} className="text-green-400" />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Self-RAG Pipeline
              </h3>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                (How your question becomes an answer)
              </span>
            </div>
            <PipelineViz pipeline={data.pipeline} />
          </div>

          {/* Config details */}
          <ConfigSection pipeline={data.pipeline} data={data} />
        </div>
      </div>
    </div>
  )
}
