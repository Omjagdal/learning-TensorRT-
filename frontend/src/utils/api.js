// src/utils/api.js — Axios + SSE client for the FastAPI backend

import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 2 min — LLM inference can be slow
})

// ── Manuals ───────────────────────────────────────────────────────────────────


export const listManuals = () => api.get('/manuals/')
export const uploadManual = (formData, { onProgress, onDone, onError } = {}) => {
  return new Promise((resolve, reject) => {
    fetch('/api/v1/manuals/upload', {
      method: 'POST',
      body: formData,
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
          onError?.(err.detail || 'Upload failed')
          reject(new Error(err.detail || 'Upload failed'))
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                if (data.stage === 'Error') {
                  onError?.(data.error || 'Ingestion error')
                  reject(new Error(data.error || 'Ingestion error'))
                  return
                } else if (data.stage === 'Done') {
                  onDone?.(data)
                  resolve(data)
                  return
                } else {
                  onProgress?.(data.stage, data.progress)
                }
              } catch {
                // skip malformed JSON
              }
            }
          }
        }
      })
      .catch((err) => {
        onError?.(err.message || 'Upload connection failed')
        reject(err)
      })
  })
}
export const deleteManual = (id) => api.delete(`/manuals/${id}`)
export const fetchSourcePage = (manualId, pageNumber) => api.get(`/sources/${manualId}/pages/${pageNumber}`)

// ── Chat (synchronous) ───────────────────────────────────────────────────────

export const sendQuery = (question, manualIds = null, topK = null) =>
  api.post('/chat/', {
    question,
    ...(manualIds?.length && { manual_ids: manualIds }),
    ...(topK && { top_k: topK }),
  })

// ── Chat (SSE streaming) ────────────────────────────────────────────────────

/**
 * Stream Self-RAG pipeline via Server-Sent Events.
 *
 * @param {string} question
 * @param {string[]|null} manualIds
 * @param {Object} callbacks
 * @param {function} callbacks.onStage  - (data) => void  — pipeline stage updates
 * @param {function} callbacks.onToken  - (data) => void  — generated text tokens
 * @param {function} callbacks.onDone   - (data) => void  — final response
 * @param {function} callbacks.onError  - (error) => void — error
 * @returns {AbortController} — call .abort() to cancel the stream
 */
export const streamQuery = (question, manualIds, image_b64, { onStage, onToken, onImages, onDone, onError }) => {
  const controller = new AbortController()

  const body = {
    question,
    ...(manualIds?.length && { manual_ids: manualIds }),
    ...(image_b64 && { image_b64 }),
  }

  fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Stream request failed' }))
        onError?.(err.detail || 'Stream request failed')
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line in buffer

        let currentEvent = null
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              switch (currentEvent) {
                case 'stage':
                  onStage?.(data)
                  break
                case 'images':
                  onImages?.(data)
                  break
                case 'token':
                  onToken?.(data)
                  break
                case 'done':
                  onDone?.(data)
                  break
                case 'error':
                  onError?.(data.detail || 'Pipeline error')
                  break
              }
            } catch {
              // skip malformed JSON
            }
            currentEvent = null
          } else if (line === '') {
            currentEvent = null
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError?.(err.message || 'Stream connection failed')
      }
    })

  return controller
}

// ── Health ────────────────────────────────────────────────────────────────────

export const getHealth = () => api.get('/health')

// ── Knowledge Base Info ──────────────────────────────────────────────────────

export const getKnowledgeBase = () => api.get('/info/knowledge-base')

