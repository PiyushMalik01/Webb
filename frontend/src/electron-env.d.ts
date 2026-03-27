export {}

declare global {
  interface Window {
    webb?: {
      version?: string
      runAction?: (action: string) => Promise<{ ok: boolean }>
    }
  }
}
