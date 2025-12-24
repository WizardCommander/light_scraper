import React, { useState, useEffect } from 'react'

interface SettingsProps {
  onClose: () => void
}

export default function Settings({ onClose }: SettingsProps) {
  const [vibiaEmail, setVibiaEmail] = useState('')
  const [vibiaPassword, setVibiaPassword] = useState('')
  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    const savedVibiaEmail = await window.electronAPI.getSetting('vibiaEmail')
    const savedVibiaPassword = await window.electronAPI.getSetting('vibiaPassword')
    const savedOpenaiApiKey = await window.electronAPI.getSetting('openaiApiKey')

    if (savedVibiaEmail) setVibiaEmail(savedVibiaEmail)
    if (savedVibiaPassword) setVibiaPassword(savedVibiaPassword)
    if (savedOpenaiApiKey) setOpenaiApiKey(savedOpenaiApiKey)
  }

  const handleSave = async () => {
    setIsSaving(true)

    await window.electronAPI.setSetting('vibiaEmail', vibiaEmail)
    await window.electronAPI.setSetting('vibiaPassword', vibiaPassword)
    await window.electronAPI.setSetting('openaiApiKey', openaiApiKey)

    setIsSaving(false)
    onClose()
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        background: 'white',
        borderRadius: '8px',
        padding: '24px',
        width: '500px',
        maxHeight: '80vh',
        overflow: 'auto'
      }}>
        <h2 style={{ marginTop: 0 }}>Settings</h2>

        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ marginBottom: '12px', fontSize: '16px' }}>Vibia Credentials</h3>
          <p style={{ fontSize: '13px', color: '#666', marginBottom: '12px' }}>
            Required for downloading datasheets and installation manuals from Vibia
          </p>

          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', fontSize: '14px' }}>
            Email
          </label>
          <input
            type="email"
            value={vibiaEmail}
            onChange={(e) => setVibiaEmail(e.target.value)}
            placeholder="your@email.com"
            style={{
              width: '100%',
              padding: '8px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              marginBottom: '12px'
            }}
          />

          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', fontSize: '14px' }}>
            Password
          </label>
          <input
            type="password"
            value={vibiaPassword}
            onChange={(e) => setVibiaPassword(e.target.value)}
            placeholder="••••••••"
            style={{
              width: '100%',
              padding: '8px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #ccc'
            }}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ marginBottom: '12px', fontSize: '16px' }}>OpenAI API Key</h3>
          <p style={{ fontSize: '13px', color: '#666', marginBottom: '12px' }}>
            Required for AI features: product descriptions, translations, and image classification (optional)
          </p>

          <input
            type="password"
            value={openaiApiKey}
            onChange={(e) => setOpenaiApiKey(e.target.value)}
            placeholder="sk-proj-..."
            style={{
              width: '100%',
              padding: '8px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #ccc'
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            disabled={isSaving}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              background: 'white',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              borderRadius: '4px',
              border: 'none',
              background: '#4CAF50',
              color: 'white',
              cursor: 'pointer'
            }}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
