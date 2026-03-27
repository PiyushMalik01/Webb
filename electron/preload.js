const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('webb', {
  version: '0.1.0',
  runAction: (action) => ipcRenderer.invoke('webb:action', action),
})

