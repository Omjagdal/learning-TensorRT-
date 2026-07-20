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
        <div className="h-12 flex items-center justify-center overflow-hidden rounded bg-white">
          <img src="/logo.png" alt="ISRA Omi" className="h-full object-contain p-1" />
        </div>
        <div className="flex flex-col justify-center">
          <span className="text-[20px] font-bold tracking-tight leading-none mb-1">
            <span style={{ color: 'var(--accent-primary)' }}>ISRA</span>{' '}
            <span style={{ color: 'var(--text-primary)' }}>Omi</span>
          </span>
          <span className="text-[13px] font-semibold tracking-wider uppercase opacity-80" style={{ color: 'var(--text-secondary)' }}></span>
        </div>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-3">
        {health && (
          <div className="hidden md:flex items-center gap-2">
            {health.offline_mode && (
              <span className="tag text-red-400 border-red-900/50 bg-red-500/10">
                <HardDrive size={11} /> Offline
              </span>
            )}
            <span className={clsx('tag', online
              ? 'text-red-500 border-red-500/20 bg-red-500/10'
              : 'text-gray-400 border-gray-500/20 bg-gray-500/10'
            )}>
              <span className={clsx('w-1.5 h-1.5 rounded-full', online ? 'bg-red-500' : 'bg-gray-400')} />
              {online ? 'Connected' : 'Offline'}
            </span>
          </div>
        )}



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

      </div>
    </header>
  )
}
