import { useEffect, useMemo, useState } from 'react'

type MenuAction = { label: string; action: string }
type MenuGroup = { label: string; items: MenuAction[] }

async function runAction(action: string) {
  try {
    await window.webb?.runAction?.(action)
  } catch {
    // no-op in browser mode
  }
}

export function DesktopTopBar() {
  const [openMenu, setOpenMenu] = useState<string | null>(null)

  useEffect(() => {
    function closeMenu() { setOpenMenu(null) }
    window.addEventListener('mousedown', closeMenu)
    return () => window.removeEventListener('mousedown', closeMenu)
  }, [])

  const menus = useMemo<MenuGroup[]>(
    () => [
      {
        label: 'File',
        items: [
          { label: 'New Window', action: 'app:new-window' },
          { label: 'Close Window', action: 'window:close' },
          { label: 'Quit', action: 'app:quit' },
        ],
      },
      {
        label: 'Edit',
        items: [
          { label: 'Undo', action: 'edit:undo' },
          { label: 'Redo', action: 'edit:redo' },
          { label: 'Cut', action: 'edit:cut' },
          { label: 'Copy', action: 'edit:copy' },
          { label: 'Paste', action: 'edit:paste' },
          { label: 'Select All', action: 'edit:select-all' },
        ],
      },
      {
        label: 'View',
        items: [
          { label: 'Reload', action: 'view:reload' },
          { label: 'Force Reload', action: 'view:force-reload' },
          { label: 'Toggle DevTools', action: 'view:devtools-toggle' },
          { label: 'Zoom In', action: 'view:zoom-in' },
          { label: 'Zoom Out', action: 'view:zoom-out' },
          { label: 'Reset Zoom', action: 'view:zoom-reset' },
          { label: 'Toggle Fullscreen', action: 'view:fullscreen-toggle' },
        ],
      },
      {
        label: 'Window',
        items: [
          { label: 'Minimize', action: 'window:minimize' },
          { label: 'Maximize / Restore', action: 'window:maximize-toggle' },
          { label: 'Close', action: 'window:close' },
        ],
      },
      { label: 'Help', items: [{ label: 'Project Home', action: 'help:project-home' }] },
    ],
    [],
  )

  return (
    <header className="desktop-topbar">
      <div className="desktop-topbar__drag flex h-10 items-center px-3">
        <div className="no-drag flex items-center gap-1">
          <div className="mr-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Webb</div>
          {menus.map((menu) => (
            <div key={menu.label} className="relative" onMouseDown={(e) => e.stopPropagation()}>
              <button
                type="button"
                className={[
                  'rounded-md px-2.5 py-1 text-sm font-medium transition',
                  openMenu === menu.label
                    ? 'bg-white/10 text-white'
                    : 'hover:bg-white/6',
                ].join(' ')}
                style={{ color: openMenu === menu.label ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                onClick={(e) => {
                  e.stopPropagation()
                  setOpenMenu((x) => (x === menu.label ? null : menu.label))
                }}
              >
                {menu.label}
              </button>

              {openMenu === menu.label ? (
                <div
                  className="no-drag absolute left-0 top-full z-[70] mt-1 w-52 rounded-lg p-1"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                >
                  {menu.items.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      className="block w-full rounded-md px-3 py-2 text-left text-sm transition hover:bg-white/6"
                      style={{ color: 'var(--text-secondary)' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        runAction(item.action)
                        setOpenMenu(null)
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </header>
  )
}
