import React, { useState, useRef } from 'react'
import { FileText, Trash2, CheckCircle, Loader2, BookOpen } from 'lucide-react'
import { deleteManual } from '../utils/api'
import clsx from 'clsx'

function ManualItem({ manual, selected, onToggle, onDelete }) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!confirm(`Delete "${manual.filename}"?`)) return
    setDeleting(true)
    try {
      await deleteManual(manual.manual_id)
      onDelete(manual.manual_id)
    } catch {
      alert('Failed to delete manual')
    } finally {
      setDeleting(false)
    }
  }

  const size = (manual.size_bytes / (1024 * 1024)).toFixed(1)

  return (
    <div
      onClick={() => onToggle(manual.manual_id)}
      className={clsx(
        'group flex items-start gap-2.5 p-2.5 rounded-md cursor-pointer transition-all',
        selected
          ? 'bg-blue-500/10 border border-blue-500/30'
          : 'hover:bg-white/5 border border-transparent'
      )}
    >
      <div className={clsx('mt-0.5 shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors',
        selected ? 'bg-blue-500 border-blue-500' : 'border-gray-600'
      )}>
        {selected && <CheckCircle size={10} className="text-white" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-200 truncate">{manual.filename}</p>
        <p className="text-xs text-gray-500 mt-0.5">
          {manual.page_count}p · {manual.chunk_count} chunks · {size}MB
        </p>
      </div>
      <button
        onClick={handleDelete}
        disabled={deleting}
        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-all"
      >
        {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
      </button>
    </div>
  )
}

export default function Sidebar({ manuals, selectedIds, onToggle, onRefresh, loading }) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const fileInputRef = useRef(null)

  const allSelected = manuals.length > 0 && manuals.every(m => selectedIds.includes(m.manual_id))

  const handleSelectAll = () => {
    if (allSelected) {
      manuals.forEach(m => selectedIds.includes(m.manual_id) && onToggle(m.manual_id))
    } else {
      manuals.forEach(m => !selectedIds.includes(m.manual_id) && onToggle(m.manual_id))
    }
  }

  const handleFileChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setUploading(true)
    setProgress(0)
    try {
      await import('../utils/api').then(m => m.uploadManual(file, setProgress))
      onRefresh()
    } catch (err) {
      alert(`Upload failed: ${err.message}`)
    } finally {
      setUploading(false)
      setProgress(0)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <aside className="w-64 shrink-0 flex flex-col border-r border-gray-800 bg-gray-900/30">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-blue-400" />
          <span className="text-sm font-semibold text-gray-200">Manuals</span>
          {loading && !uploading && <Loader2 size={12} className="ml-2 text-gray-500 animate-spin" />}
        </div>
        <div>
          <input 
            type="file" 
            accept="application/pdf" 
            className="hidden" 
            ref={fileInputRef} 
            onChange={handleFileChange}
          />
          <button 
            className="text-xs px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors disabled:opacity-50 flex items-center gap-1"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <><Loader2 size={12} className="animate-spin" /> {progress}%</>
            ) : (
              'Upload'
            )}
          </button>
        </div>
      </div>

      {/* Manual list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 pt-2">
        {manuals.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-6 px-4">
            No manuals loaded yet
          </p>
        ) : (
          <>
            {manuals.length > 1 && (
              <button
                onClick={handleSelectAll}
                className="w-full text-left px-2 py-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                {allSelected ? 'Deselect all' : 'Select all'}
              </button>
            )}
            <div className="space-y-1">
              {manuals.map(m => (
                <ManualItem
                  key={m.manual_id}
                  manual={m}
                  selected={selectedIds.includes(m.manual_id)}
                  onToggle={onToggle}
                  onDelete={onRefresh}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Footer info */}
      {selectedIds.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-500">
          Searching {selectedIds.length} of {manuals.length} manual{manuals.length !== 1 ? 's' : ''}
        </div>
      )}
    </aside>
  )
}
