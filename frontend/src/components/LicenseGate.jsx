import React, { useState, useRef } from 'react'
import { Shield, ShieldCheck, Upload, Copy, AlertTriangle, CheckCircle2, KeyRound } from 'lucide-react'
import { activateLicense } from '../utils/api'

export default function LicenseGate({ licenseData, onActivated }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [copied, setCopied] = useState(false)
  const fileRef = useRef(null)

  const machineId = licenseData?.machine_id || 'Loading...'
  const status = licenseData?.status || 'not_activated'
  const message = licenseData?.message || ''

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)
    setSuccess(null)

    try {
      const res = await activateLicense(file)
      setSuccess(res.data.message)
      // Wait a moment then reload
      setTimeout(() => onActivated?.(), 1500)
    } catch (err) {
      setError(err.response?.data?.detail || 'Activation failed. Please check your license file.')
    } finally {
      setUploading(false)
    }
  }

  const copyMachineId = () => {
    navigator.clipboard.writeText(machineId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-md mx-4">
        {/* Card */}
        <div
          className="rounded-2xl p-8 shadow-xl"
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
          }}
        >
          {/* Icon */}
          <div className="flex justify-center mb-6">
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center"
              style={{
                background: status === 'expired'
                  ? 'rgba(255, 77, 79, 0.1)'
                  : 'rgba(255, 77, 79, 0.08)',
              }}
            >
              {status === 'expired' ? (
                <AlertTriangle size={36} style={{ color: 'var(--accent-primary)' }} />
              ) : (
                <KeyRound size={36} style={{ color: 'var(--accent-primary)' }} />
              )}
            </div>
          </div>

          {/* Title */}
          <h1
            className="text-2xl font-bold text-center mb-2"
            style={{ color: 'var(--text-primary)' }}
          >
            {status === 'expired' ? 'License Expired' : 'License Activation Required'}
          </h1>

          <p
            className="text-center text-sm mb-6"
            style={{ color: 'var(--text-secondary)' }}
          >
            {status === 'expired'
              ? message
              : 'Please activate your license to use ISRA Chatbot.'}
          </p>

          {/* Machine ID */}
          <div className="mb-6">
            <label
              className="block text-xs font-semibold uppercase tracking-wider mb-2"
              style={{ color: 'var(--text-muted)' }}
            >
              Your Machine ID
            </label>
            <div
              className="flex items-center gap-2 rounded-lg px-3 py-2.5"
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border)',
              }}
            >
              <code
                className="flex-1 text-xs font-mono truncate"
                style={{ color: 'var(--text-primary)' }}
              >
                {machineId}
              </code>
              <button
                onClick={copyMachineId}
                className="shrink-0 p-1.5 rounded-md transition-colors hover:opacity-80"
                style={{ color: copied ? '#22c55e' : 'var(--text-muted)' }}
                title="Copy Machine ID"
              >
                {copied ? <CheckCircle2 size={16} /> : <Copy size={16} />}
              </button>
            </div>
            <p className="text-xs mt-1.5" style={{ color: 'var(--text-muted)' }}>
              Send this ID to your administrator to receive a license file.
            </p>
          </div>

          {/* Upload License */}
          <input
            ref={fileRef}
            type="file"
            accept=".lic"
            onChange={handleFileUpload}
            className="hidden"
          />

          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 font-semibold text-white transition-all hover:opacity-90 disabled:opacity-50"
            style={{ background: 'var(--accent-primary)' }}
          >
            {uploading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Activating...
              </>
            ) : (
              <>
                <Upload size={18} />
                Upload License File (.lic)
              </>
            )}
          </button>

          {/* Error */}
          {error && (
            <div
              className="mt-4 flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm"
              style={{
                background: 'rgba(255, 77, 79, 0.1)',
                color: 'var(--accent-primary)',
                border: '1px solid rgba(255, 77, 79, 0.2)',
              }}
            >
              <AlertTriangle size={16} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Success */}
          {success && (
            <div
              className="mt-4 flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm"
              style={{
                background: 'rgba(34, 197, 94, 0.1)',
                color: '#22c55e',
                border: '1px solid rgba(34, 197, 94, 0.2)',
              }}
            >
              <ShieldCheck size={16} className="shrink-0 mt-0.5" />
              <span>{success}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs mt-4" style={{ color: 'var(--text-muted)' }}>
          <span style={{ color: 'var(--accent-primary)' }}>ISRA</span>{' '}
          <span style={{ color: 'var(--text-primary)' }}>OMI</span> — Industrial Manual Chatbot
        </p>
      </div>
    </div>
  )
}
