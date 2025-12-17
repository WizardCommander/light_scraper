import React, { useState, useEffect } from 'react'
import type { ScraperEvent } from './types'

export default function App() {
  const [skus, setSkus] = useState('')
  const [skusFile, setSkusFile] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [downloadImages, setDownloadImages] = useState(true)
  const [downloadPdfs, setDownloadPdfs] = useState(true)
  const [translate, setTranslate] = useState(true)
  const [aiDescriptions, setAiDescriptions] = useState(false)
  const [verbose, setVerbose] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [updateAvailable, setUpdateAvailable] = useState(false)

  useEffect(() => {
    // Load saved settings
    loadSettings()

    // Set up event listeners
    window.electronAPI.onScraperLog((log) => {
      setLogs((prev) => [...prev, log])
    })

    window.electronAPI.onScraperError((error) => {
      setLogs((prev) => [...prev, `ERROR: ${error}`])
    })

    window.electronAPI.onScraperEvent((event: ScraperEvent) => {
      handleScraperEvent(event)
    })

    window.electronAPI.onUpdateAvailable(() => {
      setUpdateAvailable(true)
    })

    window.electronAPI.onUpdateDownloaded(() => {
      alert('Update downloaded! It will be installed on next launch.')
    })
  }, [])

  const loadSettings = async () => {
    const savedOutputDir = await window.electronAPI.getSetting('outputDir')
    if (savedOutputDir) setOutputDir(savedOutputDir)

    const savedDownloadImages = await window.electronAPI.getSetting('downloadImages')
    if (savedDownloadImages !== undefined) setDownloadImages(savedDownloadImages)

    const savedTranslate = await window.electronAPI.getSetting('translate')
    if (savedTranslate !== undefined) setTranslate(savedTranslate)
  }

  const handleScraperEvent = (event: ScraperEvent) => {
    if (event.type === 'scrape_start') {
      setProgress({ current: 0, total: event.data.total_skus || 0 })
    } else if (event.type === 'product_complete') {
      setProgress((prev) => ({ ...prev, current: prev.current + 1 }))
    } else if (event.type === 'scrape_complete') {
      setIsRunning(false)
      alert(`Scraping complete! ${event.data.succeeded} succeeded, ${event.data.failed} failed`)
    }
  }

  const handleBrowseOutput = async () => {
    const dir = await window.electronAPI.selectDirectory()
    if (dir) {
      setOutputDir(dir)
      await window.electronAPI.setSetting('outputDir', dir)
    }
  }

  const handleLoadFile = async () => {
    const file = await window.electronAPI.selectFile()
    if (file) {
      setSkusFile(file)
    }
  }

  const handleStart = async () => {
    if (!skus && !skusFile) {
      alert('Please enter SKUs or load from file')
      return
    }

    setIsRunning(true)
    setLogs([])
    setProgress({ current: 0, total: 0 })

    try {
      await window.electronAPI.startScraper({
        skus: skus || undefined,
        skusFile: skusFile || undefined,
        outputDir: outputDir || undefined,
        noImages: !downloadImages,
        aiDescriptions,
        noTranslate: !translate,
        verbose
      })
      // Scraper completed successfully
      setIsRunning(false)
    } catch (error) {
      alert(`Scraper failed: ${error}`)
      setIsRunning(false)
    }
  }

  const handleStop = async () => {
    await window.electronAPI.stopScraper()
    setIsRunning(false)
  }

  const progressPercent = progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', padding: '20px', gap: '20px' }}>
      {updateAvailable && (
        <div style={{ padding: '10px', background: '#4CAF50', color: 'white', borderRadius: '4px' }}>
          Update available! It will be downloaded in the background.
        </div>
      )}

      <h1 style={{ margin: 0 }}>Light Scraper</h1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Step 1: Enter Product SKUs
          </label>
          <textarea
            value={skus}
            onChange={(e) => setSkus(e.target.value)}
            placeholder="kelly, megaphone, a-tube-suspension"
            disabled={isRunning}
            style={{
              width: '100%',
              height: '80px',
              padding: '8px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #ccc'
            }}
          />
          <div style={{ marginTop: '8px', display: 'flex', gap: '10px' }}>
            <button onClick={handleLoadFile} disabled={isRunning} style={buttonStyle}>
              📁 Load from file
            </button>
            {skusFile && <span style={{ lineHeight: '32px' }}>File: {skusFile}</span>}
          </div>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
            Step 2: Select Options
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={downloadImages}
                onChange={(e) => setDownloadImages(e.target.checked)}
                disabled={isRunning}
              />
              Download images
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={downloadPdfs}
                onChange={(e) => setDownloadPdfs(e.target.checked)}
                disabled={isRunning}
              />
              Download datasheets (PDFs)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={translate}
                onChange={(e) => setTranslate(e.target.checked)}
                disabled={isRunning}
              />
              Translate to German
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={aiDescriptions}
                onChange={(e) => setAiDescriptions(e.target.checked)}
                disabled={isRunning}
              />
              Generate AI descriptions (requires API key)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={verbose}
                onChange={(e) => setVerbose(e.target.checked)}
                disabled={isRunning}
              />
              Verbose logging
            </label>
          </div>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Step 3: Output Settings
          </label>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              placeholder="Output folder (default: ./output)"
              disabled={isRunning}
              style={{
                flex: 1,
                padding: '8px',
                fontSize: '14px',
                borderRadius: '4px',
                border: '1px solid #ccc'
              }}
            />
            <button onClick={handleBrowseOutput} disabled={isRunning} style={buttonStyle}>
              Browse
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          {!isRunning ? (
            <button onClick={handleStart} style={{ ...buttonStyle, background: '#4CAF50', color: 'white' }}>
              ▶ Start Scraping
            </button>
          ) : (
            <button onClick={handleStop} style={{ ...buttonStyle, background: '#f44336', color: 'white' }}>
              ⏹ Stop
            </button>
          )}
        </div>

        {isRunning && progress.total > 0 && (
          <div>
            <div style={{ marginBottom: '5px' }}>
              Progress: {progress.current}/{progress.total} products ({progressPercent}%)
            </div>
            <div style={{ width: '100%', height: '20px', background: '#e0e0e0', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${progressPercent}%`,
                  height: '100%',
                  background: '#4CAF50',
                  transition: 'width 0.3s'
                }}
              />
            </div>
          </div>
        )}
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <h3 style={{ marginBottom: '10px' }}>Logs</h3>
        <div
          style={{
            flex: 1,
            background: '#1e1e1e',
            color: '#d4d4d4',
            padding: '10px',
            borderRadius: '4px',
            fontFamily: 'Consolas, Monaco, monospace',
            fontSize: '11px',
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            lineHeight: '1.4'
          }}
        >
          {logs
            .filter((log, i, arr) => {
              // Remove duplicate consecutive logs
              return i === 0 || log !== arr[i - 1]
            })
            .map((log, i) => {
              // Clean up log formatting
              let cleanLog = log
                .replace(/\x1b\[[0-9;]*m/g, '') // Remove ANSI color codes
                .replace(/^ERROR:\s+/g, '') // Remove ERROR: prefix first
                .replace(/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+\|\s+/g, '') // Remove timestamp prefix
                .replace(/\s+\|\s+INFO\s+\|\s+/g, ' | ') // Clean up log level separators
                .replace(/\s+\|\s+SUCCESS\s+\|\s+/g, ' | ')
                .replace(/\s+\|\s+ERROR\s+\|\s+/g, ' | ')
                .trim()

              // Skip empty logs
              if (!cleanLog) return null

              // Determine color based on content (only if explicitly marked)
              const isSuccess = cleanLog.includes('SUCCESS') || cleanLog.includes('Successfully')
              const isError = cleanLog.includes('ERROR') || cleanLog.includes('Failed') || cleanLog.includes('Error:')

              const color = isSuccess ? '#51cf66' : isError ? '#ff6b6b' : '#ffffff'

              return (
                <div key={i} style={{ color, marginBottom: '2px' }}>{cleanLog}</div>
              )
            })}
        </div>
      </div>
    </div>
  )
}

const buttonStyle: React.CSSProperties = {
  padding: '8px 16px',
  fontSize: '14px',
  borderRadius: '4px',
  border: '1px solid #ccc',
  background: 'white',
  cursor: 'pointer'
}
