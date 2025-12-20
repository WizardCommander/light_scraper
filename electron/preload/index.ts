import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  selectFile: () => ipcRenderer.invoke('select-file'),
  getSetting: (key: string) => ipcRenderer.invoke('get-setting', key),
  setSetting: (key: string, value: any) => ipcRenderer.invoke('set-setting', key, value),
  startScraper: (options: any) => ipcRenderer.invoke('start-scraper', options),
  stopScraper: () => ipcRenderer.invoke('stop-scraper'),

  // Event listeners now return unsubscribe functions
  onScraperLog: (callback: (log: string) => void) => {
    const listener = (_event: IpcRendererEvent, log: string) => callback(log)
    ipcRenderer.on('scraper-log', listener)
    return () => ipcRenderer.removeListener('scraper-log', listener)
  },
  onScraperError: (callback: (error: string) => void) => {
    const listener = (_event: IpcRendererEvent, error: string) => callback(error)
    ipcRenderer.on('scraper-error', listener)
    return () => ipcRenderer.removeListener('scraper-error', listener)
  },
  onScraperEvent: (callback: (event: any) => void) => {
    const listener = (_event: IpcRendererEvent, event: any) => callback(event)
    ipcRenderer.on('scraper-event', listener)
    return () => ipcRenderer.removeListener('scraper-event', listener)
  },
  onUpdateAvailable: (callback: () => void) => {
    const listener = () => callback()
    ipcRenderer.on('update-available', listener)
    return () => ipcRenderer.removeListener('update-available', listener)
  },
  onUpdateDownloaded: (callback: () => void) => {
    const listener = () => callback()
    ipcRenderer.on('update-downloaded', listener)
    return () => ipcRenderer.removeListener('update-downloaded', listener)
  }
})
