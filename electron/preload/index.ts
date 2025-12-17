import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  selectFile: () => ipcRenderer.invoke('select-file'),
  getSetting: (key: string) => ipcRenderer.invoke('get-setting', key),
  setSetting: (key: string, value: any) => ipcRenderer.invoke('set-setting', key, value),
  startScraper: (options: any) => ipcRenderer.invoke('start-scraper', options),
  stopScraper: () => ipcRenderer.invoke('stop-scraper'),
  onScraperLog: (callback: (log: string) => void) => {
    ipcRenderer.on('scraper-log', (_event, log) => callback(log))
  },
  onScraperError: (callback: (error: string) => void) => {
    ipcRenderer.on('scraper-error', (_event, error) => callback(error))
  },
  onScraperEvent: (callback: (event: any) => void) => {
    ipcRenderer.on('scraper-event', (_event, event) => callback(event))
  },
  onUpdateAvailable: (callback: () => void) => {
    ipcRenderer.on('update-available', callback)
  },
  onUpdateDownloaded: (callback: () => void) => {
    ipcRenderer.on('update-downloaded', callback)
  }
})
