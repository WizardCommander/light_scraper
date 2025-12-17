export interface ElectronAPI {
  selectDirectory: () => Promise<string | null>
  selectFile: () => Promise<string | null>
  getSetting: (key: string) => Promise<any>
  setSetting: (key: string, value: any) => Promise<void>
  startScraper: (options: ScraperOptions) => Promise<{ success: boolean }>
  stopScraper: () => Promise<{ success: boolean; message?: string }>
  onScraperLog: (callback: (log: string) => void) => void
  onScraperError: (callback: (error: string) => void) => void
  onScraperEvent: (callback: (event: ScraperEvent) => void) => void
  onUpdateAvailable: (callback: () => void) => void
  onUpdateDownloaded: (callback: () => void) => void
}

export interface ScraperOptions {
  skus?: string
  skusFile?: string
  outputDir?: string
  noImages?: boolean
  aiDescriptions?: boolean
  noTranslate?: boolean
  verbose?: boolean
}

export interface ScraperEvent {
  type: string
  data: any
  timestamp: string
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}
