import React, { useState } from 'react'
import { ArrowLeft, ZoomIn } from 'lucide-react'
import { DiagramLightbox } from './Message' // Need to export DiagramLightbox from Message.jsx if possible, or duplicate/move it.

export default function FolderView({ data, onBack }) {
  const { gallery, title } = data
  const [lightboxIndex, setLightboxIndex] = useState(null)

  return (
    <div className="flex flex-col h-full w-full bg-[var(--bg-primary)] z-10 relative overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="flex items-center px-6 py-4 border-b border-[var(--border)] bg-[var(--bg-secondary)] shrink-0">
        <button 
          onClick={onBack}
          className="flex items-center gap-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors px-3 py-1.5 rounded-lg hover:bg-[var(--bg-hover)]"
        >
          <ArrowLeft size={18} />
          <span className="font-medium text-sm">Back to Chat</span>
        </button>
        <div className="ml-6 flex items-center gap-3">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Image Stack</h2>
          <span className="text-xs font-mono text-[var(--text-muted)] bg-[var(--bg-tertiary)] px-2 py-1 rounded">
            {gallery.length} Images
          </span>
        </div>
      </div>

      {/* Grid Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto diagram-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '20px' }}>
          {gallery.map((img, i) => (
            <div
              key={img.url}
              className="diagram-thumbnail-card bg-[var(--bg-secondary)]"
              style={{ animationDelay: `${i * 40}ms` }}
              onClick={() => setLightboxIndex(i)}
            >
              <div className="diagram-thumbnail-wrapper" style={{ aspectRatio: '3/4' }}>
                <img
                  src={img.url}
                  alt={`Diagram — Page ${img.page}`}
                  className="diagram-thumbnail-img"
                  loading="lazy"
                />
                <div className="diagram-thumbnail-overlay">
                  <ZoomIn size={24} className="text-white" />
                </div>
              </div>
              <div className="diagram-thumbnail-label">
                <span className="text-[12px] font-mono text-[var(--text-muted)]">
                  p.{img.page}
                </span>
                <span className="text-[11px] truncate flex-1 text-[var(--text-muted)]" title={img.hierarchy}>
                  {(img.hierarchy || '').split(' > ').pop()}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {lightboxIndex !== null && (
        <DiagramLightbox
          images={gallery}
          currentIndex={lightboxIndex}
          onChangeIndex={setLightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </div>
  )
}
