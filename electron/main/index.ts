import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import { autoUpdater } from 'electron-updater'
import Store from 'electron-store'

const store = new Store()

let mainWindow: BrowserWindow | null = null
let scraperProcess: ChildProcess | null = null

/**
 * Get platform-specific Python executable path
 */
function getPythonExecutablePath(): string {
  const isWindows = process.platform === 'win32'
  const isMac = process.platform === 'darwin'

  if (process.env.NODE_ENV === 'development') {
    // Development: use virtual environment
    const venvPath = path.join(__dirname, '../../venv')
    if (isWindows) {
      return path.join(venvPath, 'Scripts/python.exe')
    } else {
      return path.join(venvPath, 'bin/python')
    }
  } else {
    // Production: use bundled executable
    const resourcesPath = process.resourcesPath
    if (isWindows) {
      return path.join(resourcesPath, 'python/scraper.exe')
    } else if (isMac) {
      return path.join(resourcesPath, 'python/scraper')
    } else {
      // Linux
      return path.join(resourcesPath, 'python/scraper')
    }
  }
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    title: 'Light Scraper',
    autoHideMenuBar: true
  })

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
    if (scraperProcess) {
      scraperProcess.kill()
    }
  })
}

app.whenReady().then(() => {
  createWindow()

  // Check for updates
  if (process.env.NODE_ENV !== 'development') {
    autoUpdater.checkForUpdatesAndNotify()

    // Check every 2 hours
    setInterval(() => {
      autoUpdater.checkForUpdates()
    }, 2 * 60 * 60 * 1000)
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// IPC Handlers

ipcMain.handle('select-directory', async () => {
  if (!mainWindow) return null

  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  })

  if (result.canceled) {
    return null
  }

  return result.filePaths[0]
})

ipcMain.handle('select-file', async () => {
  if (!mainWindow) return null

  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Text Files', extensions: ['txt'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  })

  if (result.canceled) {
    return null
  }

  return result.filePaths[0]
})

ipcMain.handle('get-setting', (_event, key: string) => {
  return store.get(key)
})

ipcMain.handle('set-setting', (_event, key: string, value: any) => {
  store.set(key, value)
})

ipcMain.handle('start-scraper', (_event, options) => {
  return new Promise((resolve, reject) => {
    if (scraperProcess) {
      reject(new Error('Scraper is already running'))
      return
    }

    // Get Python executable path (cross-platform)
    const pythonExe = getPythonExecutablePath()

    // Build arguments
    const args = ['-m', 'src.cli']

    if (process.env.NODE_ENV !== 'development') {
      // In production, use bundled executable (no -m flag)
      args.length = 0
    }

    args.push('--manufacturer', 'lodes')

    if (options.skus) {
      args.push('--skus', options.skus)
    } else if (options.skusFile) {
      args.push('--skus-file', options.skusFile)
    }

    if (options.outputDir) {
      args.push('--output', options.outputDir)
    }

    if (options.noImages) {
      args.push('--no-images')
    }

    if (options.aiDescriptions) {
      args.push('--ai-descriptions')
    }

    if (options.noTranslate) {
      args.push('--no-translate')
    }

    if (options.verbose) {
      args.push('--verbose')
    }

    // Spawn Python process
    scraperProcess = spawn(pythonExe, args, {
      cwd: process.env.NODE_ENV === 'development'
        ? path.join(__dirname, '../..')
        : process.resourcesPath
    })

    scraperProcess.stdout?.on('data', (data) => {
      const output = data.toString()
      const lines = output.split('\n')

      for (const line of lines) {
        if (line.trim()) {
          // Check if it's a structured event
          if (line.startsWith('EVENT:')) {
            try {
              const event = JSON.parse(line.substring(6))
              mainWindow?.webContents.send('scraper-event', event)
            } catch (e) {
              // If JSON parse fails, treat as regular log
              mainWindow?.webContents.send('scraper-log', line)
            }
          } else {
            // Regular log line
            mainWindow?.webContents.send('scraper-log', line)
          }
        }
      }
    })

    scraperProcess.stderr?.on('data', (data) => {
      const error = data.toString()
      mainWindow?.webContents.send('scraper-error', error)
    })

    scraperProcess.on('close', (code) => {
      scraperProcess = null
      if (code === 0) {
        resolve({ success: true })
      } else {
        reject(new Error(`Scraper exited with code ${code}`))
      }
    })

    scraperProcess.on('error', (error) => {
      scraperProcess = null
      reject(error)
    })
  })
})

ipcMain.handle('stop-scraper', () => {
  if (scraperProcess) {
    scraperProcess.kill()
    scraperProcess = null
    return { success: true }
  }
  return { success: false, message: 'No scraper process running' }
})

// Auto-updater events
autoUpdater.on('update-available', () => {
  mainWindow?.webContents.send('update-available')
})

autoUpdater.on('update-downloaded', () => {
  mainWindow?.webContents.send('update-downloaded')
})

autoUpdater.on('error', (error) => {
  console.error('Auto-updater error:', error)
})
