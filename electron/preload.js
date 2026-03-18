const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('webb', {
  version: '0.1.0',
})

