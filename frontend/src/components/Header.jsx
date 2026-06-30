import React from 'react'
import { Database, HardDrive, Sun, Moon } from 'lucide-react'
import clsx from 'clsx'

export default function Header({ health, onClear, hasMessages, onShowKnowledge, theme, onToggleTheme }) {
  const online = health?.status === 'ok'
  const isLight = theme === 'light'

  return (
    <header className="flex items-center justify-between px-6 py-4 relative z-50" style={{ background: 'var(--bg-primary)' }}>
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <img src="/logo.png" alt="Logo" className="w-full h-full object-contain p-1" />
        </div>
        <span className="text-[15px] font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>ISRA Vision Chatbot Assistant</span>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-3">
        {health && (
          <div className="hidden md:flex items-center gap-2">
            {health.offline_mode && (
              <span className="tag text-emerald-400 border-emerald-900/50 bg-emerald-500/10">
                <HardDrive size={11} /> Offline
              </span>
            )}
            <span className={clsx('tag', online
              ? 'text-emerald-500 border-emerald-500/20 bg-emerald-500/10'
              : 'text-red-400 border-red-500/20 bg-red-500/10'
            )}>
              <span className={clsx('w-1.5 h-1.5 rounded-full', online ? 'bg-emerald-400' : 'bg-red-400')} />
              {online ? 'Connected' : 'Offline'}
            </span>
          </div>
        )}

        <button
          onClick={onShowKnowledge}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-[13px] font-medium transition-all"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-tertiary)'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        >
          <Database size={14} />
          Knowledge
        </button>

        {hasMessages && (
          <button
            onClick={onClear}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-[13px] font-medium text-red-400/80 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            Clear
          </button>
        )}

        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          className="w-8 h-8 rounded-xl flex items-center justify-center transition-all"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          title={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {isLight ? <Moon size={15} /> : <Sun size={15} />}
        </button>

        {/* User avatar */}
        <div className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-semibold ml-1"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          M
        </div>
      </div>
    </header>
  )
}
