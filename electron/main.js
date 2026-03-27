const path = require('path')
const { app, BrowserWindow, Menu, shell, ipcMain } = require('electron')

const DEV_URL = process.env.ELECTRON_START_URL || 'http://localhost:5173'

function createAppMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'New Window',
          accelerator: 'CmdOrCtrl+N',
          click: () => createWindow(),
        },
        { type: 'separator' },
        { role: 'close' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Window',
      submenu: [{ role: 'minimize' }, { role: 'maximize' }, { role: 'front' }],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Webb Project Home',
          click: async () => {
            await shell.openExternal('https://github.com')
          },
        },
      ],
    },
  ]

  if (process.platform === 'darwin') {
    template.unshift({
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    })
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

function getFocusedWindow() {
  return BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0] || null
}

function registerIpcActions() {
  ipcMain.handle('webb:action', (_event, action) => {
    const win = getFocusedWindow()
    if (!win) return { ok: false }

    const wc = win.webContents

    switch (action) {
      case 'app:new-window':
        createWindow()
        return { ok: true }
      case 'app:quit':
        app.quit()
        return { ok: true }
      case 'window:minimize':
        win.minimize()
        return { ok: true }
      case 'window:maximize-toggle':
        if (win.isMaximized()) win.unmaximize()
        else win.maximize()
        return { ok: true }
      case 'window:close':
        win.close()
        return { ok: true }
      case 'edit:undo':
        wc.undo()
        return { ok: true }
      case 'edit:redo':
        wc.redo()
        return { ok: true }
      case 'edit:cut':
        wc.cut()
        return { ok: true }
      case 'edit:copy':
        wc.copy()
        return { ok: true }
      case 'edit:paste':
        wc.paste()
        return { ok: true }
      case 'edit:select-all':
        wc.selectAll()
        return { ok: true }
      case 'view:reload':
        wc.reload()
        return { ok: true }
      case 'view:force-reload':
        wc.reloadIgnoringCache()
        return { ok: true }
      case 'view:devtools-toggle':
        wc.toggleDevTools()
        return { ok: true }
      case 'view:zoom-in':
        wc.setZoomLevel(wc.getZoomLevel() + 0.5)
        return { ok: true }
      case 'view:zoom-out':
        wc.setZoomLevel(wc.getZoomLevel() - 0.5)
        return { ok: true }
      case 'view:zoom-reset':
        wc.setZoomLevel(0)
        return { ok: true }
      case 'view:fullscreen-toggle':
        win.setFullScreen(!win.isFullScreen())
        return { ok: true }
      case 'help:project-home':
        shell.openExternal('https://github.com')
        return { ok: true }
      default:
        return { ok: false }
    }
  })
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 720,
    frame: true,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#00000000',
      symbolColor: '#ffffff',
      height: 34,
    },
    transparent: true,
    backgroundColor: '#00000000',
    hasShadow: true,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.setMenuBarVisibility(false)

  if (process.env.NODE_ENV === 'development') {
    win.loadURL(DEV_URL)
    win.webContents.openDevTools({ mode: 'detach' })
  } else {
    win.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'))
  }
}

app.whenReady().then(() => {
  createAppMenu()
  registerIpcActions()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

