import React, { useState, useEffect } from 'react'
import type { ScraperEvent } from './types'
import { cleanLogMessage, getLogColor, removeDuplicates } from './logUtils'
import { ToastContainer, useToast } from './Toast'

export default function App() {
  const toast = useToast()
  const [manufacturer, setManufacturer] = useState('lodes')
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

    // Set up event listeners with cleanup
    const unsubscribeLog = window.electronAPI.onScraperLog((log) => {
      setLogs((prev) => [...prev, log])
    })

    const unsubscribeError = window.electronAPI.onScraperError((error) => {
      setLogs((prev) => [...prev, `ERROR: ${error}`])
    })

    const unsubscribeEvent = window.electronAPI.onScraperEvent((event: ScraperEvent) => {
      handleScraperEvent(event)
    })

    const unsubscribeUpdateAvailable = window.electronAPI.onUpdateAvailable(() => {
      setUpdateAvailable(true)
    })

    const unsubscribeUpdateDownloaded = window.electronAPI.onUpdateDownloaded(() => {
      toast.success('Update downloaded! It will be installed on next launch.')
    })

    // Cleanup function
    return () => {
      unsubscribeLog()
      unsubscribeError()
      unsubscribeEvent()
      unsubscribeUpdateAvailable()
      unsubscribeUpdateDownloaded()
    }
  }, [])

  const loadSettings = async () => {
    const savedManufacturer = await window.electronAPI.getSetting('manufacturer')
    if (savedManufacturer) setManufacturer(savedManufacturer)

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
      const message = `Scraping complete! ${event.data.succeeded} succeeded, ${event.data.failed} failed`
      if (event.data.failed > 0) {
        toast.info(message)
      } else {
        toast.success(message)
      }
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
      toast.error('Please enter SKUs or load from file')
      return
    }

    setIsRunning(true)
    setLogs([])
    setProgress({ current: 0, total: 0 })

    try {
      await window.electronAPI.startScraper({
        manufacturer,
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
      toast.error(`Scraper failed: ${error}`)
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
    <>
      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismissToast} />
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
            Manufacturer
          </label>
          <select
            value={manufacturer}
            onChange={async (e) => {
              const newManufacturer = e.target.value
              setManufacturer(newManufacturer)
              await window.electronAPI.setSetting('manufacturer', newManufacturer)
            }}
            disabled={isRunning}
            style={{
              width: '200px',
              padding: '8px',
              fontSize: '14px',
              borderRadius: '4px',
              border: '1px solid #ccc'
            }}
          >
            <option value="lodes">Lodes</option>
            <option value="vibia">Vibia</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Step 1: Enter Product SKUs
          </label>
          <textarea
            value={skus}
            onChange={(e) => setSkus(e.target.value)}
            placeholder={manufacturer === 'lodes'
              ? "kelly, megaphone, a-tube-suspension"
              : "circus, aura, break"
            }
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
            <button onClick={handleStart} style={{ ...buttonStyle, background: '#FF9800', color: 'white' }}>
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
          {removeDuplicates(logs).map((log, i) => {
            const cleanLog = cleanLogMessage(log)
            if (!cleanLog) return null

            return (
              <div key={i} style={{ color: getLogColor(cleanLog), marginBottom: '2px' }}>
                {cleanLog}
              </div>
            )
          })}
        </div>
      </div>
      </div>
    </>
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
