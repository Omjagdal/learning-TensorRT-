import React, { useState, useRef } from 'react'
import { FileText, Loader2, BookOpen, ChevronLeft, ChevronRight, Trash2, Upload, Star } from 'lucide-react'
import clsx from 'clsx'
import { uploadManual } from '../utils/api'

function BookmarkItem({ bookmark, onSelect, onRemove }) {
  const handleRemove = (e) => {
    e.stopPropagation()
    onRemove(bookmark)
  }

  return (
    <div
      onClick={() => onSelect(bookmark)}
      className="group flex flex-col gap-1.5 p-3 rounded-xl cursor-pointer transition-all duration-200 hover:bg-[var(--bg-tertiary)] border border-transparent"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-tight text-[var(--text-primary)] line-clamp-2">
          {bookmark.question}
        </p>
        <button
          onClick={handleRemove}
          className="opacity-0 group-hover:opacity-100 shrink-0 p-1 rounded-md hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400 transition-all"
          title="Remove bookmark"
        >
          <Trash2 size={12} />
        </button>
      </div>
      <p className="text-xs text-[var(--text-muted)] line-clamp-1 opacity-80">
        {bookmark.answer}
      </p>
      {bookmark.savedBy && (
        <p className="text-[10px] text-yellow-500/80 mt-0.5">
          Saved by {bookmark.savedBy}
        </p>
      )}
    </div>
  )
}

function ManualItem({ manual, isSelected, onToggle, onDelete }) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!confirm(`Delete "${manual.filename || manual.file_name}"?`)) return
    setDeleting(true)
    try {
      await onDelete(manual.manual_id)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div
      onClick={() => onToggle(manual.manual_id)}
      className={clsx(
        'group flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all duration-200',
        isSelected
          ? 'bg-transparent border border-[var(--border-hover)]'
          : 'hover:bg-[var(--bg-tertiary)] border border-transparent'
      )}
    >
      <div className={clsx('mt-0.5 shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors',
        isSelected ? 'bg-[var(--text-secondary)] border-[var(--text-secondary)]' : 'border-[var(--border)]'
      )}>
        {isSelected && <div className="w-1.5 h-1.5 bg-white rounded-sm" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className={clsx('text-sm font-medium truncate transition-colors',
          isSelected ? 'text-[var(--text-primary)]' : ''
        )} style={isSelected ? {} : { color: 'var(--text-secondary)' }}>
          {manual.filename || manual.file_name}
        </p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
          {manual.chunk_count} chunks indexed
        </p>
      </div>
      <button
        onClick={handleDelete}
        disabled={deleting}
        className="opacity-0 group-hover:opacity-100 shrink-0 mt-0.5 p-1 rounded-md hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400 transition-all"
        title="Delete manual"
      >
        {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
      </button>
    </div>
  )
}

export default function Sidebar({ manuals, selectedIds, onToggle, onRefresh, loading, onDelete, bookmarks = [], onSelectBookmark, onRemoveBookmark }) {
  const [isOpen, setIsOpen] = useState(true)
  const [activeTab, setActiveTab] = useState('manuals') // 'manuals' | 'bookmarks'
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStage, setUploadStage] = useState('')
  const fileInputRef = useRef(null)

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Only PDF files are accepted.')
      return
    }

    const includeImages = window.confirm(
      'Would you also like to extract and embed images from this manual?\n\n' +
      'Click OK to include images (slower).\n' +
      'Click Cancel to extract text only (faster).'
    )

    setUploading(true)
    setUploadProgress(0)
    setUploadStage('Uploading file...')
    const formData = new FormData()
    formData.append('file', file)
    formData.append('include_images', includeImages)

    try {
      await uploadManual(formData, {
        onProgress: (stage, progress) => {
          setUploadStage(stage)
          setUploadProgress(progress)
        },
        onDone: () => {
          setUploadStage('Done')
          setUploadProgress(100)
        }
      })
      await onRefresh()
    } catch (err) {
      alert('Upload failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setUploading(false)
      setUploadStage('')
      setUploadProgress(0)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleSelectAll = () => {
    const allSelected = manuals.length > 0 && manuals.every(m => selectedIds.includes(m.manual_id))
    if (allSelected) {
      manuals.forEach(m => selectedIds.includes(m.manual_id) && onToggle(m.manual_id))
    } else {
      manuals.forEach(m => !selectedIds.includes(m.manual_id) && onToggle(m.manual_id))
    }
  }

  return (
    <aside className={clsx(
      'w-64 shrink-0 flex flex-col transition-all duration-300 z-20 relative',
      !isOpen && '-ml-64'
    )} style={{ background: 'var(--bg-secondary)', borderRight: '1px solid var(--border)' }}>
      {/* Toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="absolute -right-4 top-5 w-7 h-7 rounded-lg flex items-center justify-center z-50 transition-colors"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
      >
        {isOpen ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
      </button>

      {/* Header */}
      <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between mb-0.5">
          <div className="flex items-center gap-2">
            <BookOpen size={15} style={{ color: 'var(--text-muted)' }} />
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Manuals</span>
            {(loading || uploading) && <Loader2 size={12} className="ml-1 animate-spin" style={{ color: 'var(--text-muted)' }} />}
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="p-1 rounded-md hover:bg-[var(--bg-tertiary)] transition-colors"
            title="Upload PDF manual"
            style={{ color: 'var(--text-muted)' }}
          >
            <Upload size={14} />
          </button>
          <input
            type="file"
            accept=".pdf"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="hidden"
          />
        </div>
        <div className="flex px-4 pt-2 gap-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <button
            onClick={() => setActiveTab('manuals')}
            className={clsx('pb-2 text-sm font-medium transition-colors border-b-2', activeTab === 'manuals' ? 'border-red-500 text-red-500' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]')}
          >
            Manuals
          </button>
          <button
            onClick={() => setActiveTab('bookmarks')}
            className={clsx('pb-2 text-sm font-medium transition-colors border-b-2 flex items-center gap-1', activeTab === 'bookmarks' ? 'border-yellow-500 text-yellow-400' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]')}
          >
            <Star size={13} className={clsx(activeTab === 'bookmarks' && 'fill-yellow-400')} />
            Bookmarks
          </button>
        </div>
      </div>

      {/* Upload Progress */}
      {uploading && (
        <div className="px-5 py-3" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-tertiary)' }}>
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[10px] font-medium truncate pr-2" style={{ color: 'var(--text-muted)' }}>{uploadStage}</span>
            <span className="text-[10px] font-medium" style={{ color: 'var(--text-muted)' }}>{uploadProgress}%</span>
          </div>
          <div className="w-full h-1.5 bg-gray-500/20 rounded-full overflow-hidden">
            <div 
              className="h-full bg-red-500 transition-all duration-300 ease-out" 
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1 mt-2">
        {activeTab === 'manuals' ? (
          <>
            {manuals.length === 0 && !loading ? (
              <div className="text-center p-6 text-[13px]" style={{ color: 'var(--text-muted)' }}>
                No manuals indexed yet
              </div>
            ) : (
              <>
                {manuals.length > 1 && (
                  <button
                    onClick={handleSelectAll}
                    className="w-full text-left px-3 py-1.5 text-[11px] transition-colors font-medium uppercase tracking-wider"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {selectedIds.length === manuals.length ? 'Deselect all' : 'Select all'}
                  </button>
                )}
                {manuals.map(m => (
                  <ManualItem
                    key={m.manual_id}
                    manual={m}
                    isSelected={selectedIds.includes(m.manual_id)}
                    onToggle={onToggle}
                    onDelete={onDelete}
                  />
                ))}
              </>
            )}
          </>
        ) : (
          /* Bookmarks List */
          <>
            {bookmarks.length === 0 ? (
              <div className="text-center p-6 text-[13px]" style={{ color: 'var(--text-muted)' }}>
                No bookmarks saved yet.<br />
                <span className="text-[11px] opacity-70 mt-2 block">Click the star icon on any answer to save it here for quick access.</span>
              </div>
            ) : (
              bookmarks.map(b => (
                <BookmarkItem
                  key={b.id}
                  bookmark={b}
                  onSelect={onSelectBookmark}
                  onRemove={onRemoveBookmark}
                />
              ))
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="px-5 py-4 space-y-3" style={{ borderTop: '1px solid var(--border)' }}>
        {selectedIds.length > 0 && (
          <div className="text-[11px] font-medium" style={{ color: 'var(--text-muted)' }}>
            Searching {selectedIds.length} of {manuals.length} manual{manuals.length !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </aside>
  )
}
