import React from 'react'
import { Cpu, Wifi, WifiOff, Zap } from 'lucide-react'
import clsx from 'clsx'

export default function Header({ health, onClear, hasMessages }) {
  const online = health?.status === 'ok'

  return (
    <header className="flex items-center gap-3 px-5 py-3 border-b border-gray-800 bg-gray-900/70 backdrop-blur">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-md bg-blue-500/20 border border-blue-500/30
                        flex items-center justify-center">
          <Zap size={14} className="text-blue-400" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-gray-100 leading-none">ManualMind</h1>
          <p className="text-xs text-gray-600 leading-none mt-0.5">Machine Manual Chatbot</p>
        </div>
      </div>

      {/* Status pills */}
      <div className="flex items-center gap-2 ml-auto">
        {health && (
          <>
            <div className={clsx('flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border',
              online
                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                : 'bg-red-500/10 text-red-400 border-red-500/20'
            )}>
              {online ? <Wifi size={10} /> : <WifiOff size={10} />}
              {online ? 'Online' : 'Offline'}
            </div>
            <div className={clsx('flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border',
              health.llm_loaded
                ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                : 'bg-gray-700/50 text-gray-500 border-gray-700'
            )}>
              <Cpu size={10} />
              {health.llm_loaded ? 'LLM ready' : 'LLM loading…'}
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs
                            border border-gray-700/50 text-gray-500">
              {health.indexed_manuals} manual{health.indexed_manuals !== 1 ? 's' : ''}
            </div>
          </>
        )}
        {hasMessages && (
          <button onClick={onClear} className="btn-ghost text-xs">Clear chat</button>
        )}
      </div>
    </header>
  )
}
