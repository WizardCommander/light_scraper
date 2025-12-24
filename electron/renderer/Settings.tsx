import React, { useState, useEffect } from 'react'

interface SettingsProps {
  onClose: () => void
}

export default function Settings({ onClose }: SettingsProps) {
  const [vibiaEmail, setVibiaEmail] = useState('')
  const [vibiaPassword, setVibiaPassword] = useState('')
  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [updateStatus, setUpdateStatus] = useState<any>(null)
  const [isCheckingUpdates, setIsCheckingUpdates] = useState(false)

  useEffect(() => {
    loadSettings()

    // Listen for update status events
    const unsubscribe = window.electronAPI.onUpdateStatus((status: any) => {
      setUpdateStatus(status)
      setIsCheckingUpdates(status.status === 'checking')
    })

    return () => {
      unsubscribe()
    }
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

  const handleCheckForUpdates = async () => {
    setIsCheckingUpdates(true)
    setUpdateStatus({ status: 'checking', message: 'Checking for updates...' })

    try {
      const result = await window.electronAPI.checkForUpdates()
      // Status will be updated via the event listener
    } catch (error) {
      setUpdateStatus({
        status: 'error',
        message: 'Failed to check for updates'
      })
      setIsCheckingUpdates(false)
    }
  }

  const handleInstallUpdate = async () => {
    await window.electronAPI.installUpdate()
    // App will restart after this
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

        <div style={{ marginBottom: '20px', paddingTop: '20px', borderTop: '1px solid #eee' }}>
          <h3 style={{ marginBottom: '12px', fontSize: '16px' }}>Software Updates</h3>
          <p style={{ fontSize: '13px', color: '#666', marginBottom: '12px' }}>
            Check for the latest version of Light Scraper
          </p>

          <button
            onClick={handleCheckForUpdates}
            disabled={isCheckingUpdates}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #2196F3',
              background: 'white',
              color: '#2196F3',
              cursor: isCheckingUpdates ? 'not-allowed' : 'pointer',
              opacity: isCheckingUpdates ? 0.6 : 1
            }}
          >
            {isCheckingUpdates ? 'Checking...' : 'Check for Updates'}
          </button>

          {updateStatus && (
            <div style={{
              marginTop: '12px',
              padding: '12px',
              borderRadius: '4px',
              background: updateStatus.status === 'error' ? '#ffebee' :
                          updateStatus.status === 'downloaded' ? '#e8f5e9' :
                          updateStatus.status === 'not-available' ? '#f5f5f5' :
                          '#e3f2fd',
              border: `1px solid ${
                updateStatus.status === 'error' ? '#ef5350' :
                updateStatus.status === 'downloaded' ? '#66bb6a' :
                updateStatus.status === 'not-available' ? '#ccc' :
                '#2196F3'
              }`
            }}>
              <p style={{ margin: 0, fontSize: '14px', fontWeight: '500' }}>
                {updateStatus.message}
              </p>
              {updateStatus.percent !== undefined && (
                <div style={{
                  marginTop: '8px',
                  height: '6px',
                  background: '#e0e0e0',
                  borderRadius: '3px',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    width: `${updateStatus.percent}%`,
                    height: '100%',
                    background: '#2196F3',
                    transition: 'width 0.3s ease'
                  }} />
                </div>
              )}
              {updateStatus.status === 'downloaded' && (
                <button
                  onClick={handleInstallUpdate}
                  style={{
                    marginTop: '12px',
                    padding: '6px 12px',
                    fontSize: '13px',
                    borderRadius: '4px',
                    border: 'none',
                    background: '#66bb6a',
                    color: 'white',
                    cursor: 'pointer',
                    fontWeight: '500'
                  }}
                >
                  Restart and Install
                </button>
              )}
            </div>
          )}
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
