import { UserButton, useUser } from '@clerk/react'
import { BookOpen, Database, LayoutDashboard, RotateCcw, ShieldAlert } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import { FictionalBadge } from './FictionalBadge'

const NAV = [
  { to: '/', label: 'Briefing', icon: LayoutDashboard, end: true },
  { to: '/recovery', label: 'Lead Recovery', icon: RotateCcw },
  { to: '/risk', label: 'Risk', icon: ShieldAlert },
  { to: '/knowledge', label: 'Knowledge', icon: BookOpen },
  { to: '/data', label: 'Data', icon: Database },
]

export function AppShell() {
  const { user } = useUser()

  return (
    <div className="flex min-h-screen bg-neutral-50">
      <aside className="flex w-60 shrink-0 flex-col bg-navy-800 text-neutral-0">
        <div className="border-b border-navy-700 px-5 py-5">
          <p className="text-xs font-medium tracking-wide text-navy-300 uppercase">Lumora Learning</p>
          <h1 className="mt-1 text-lg font-semibold text-white">Revenue Recovery</h1>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                [
                  'relative flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition',
                  isActive
                    ? 'bg-navy-900 text-white before:absolute before:top-1 before:bottom-1 before:left-0 before:w-[3px] before:rounded-r before:bg-indigo-500'
                    : 'text-navy-200 hover:bg-navy-900/60 hover:text-white',
                ].join(' ')
              }
            >
              <Icon className="size-4 shrink-0" strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-navy-700 p-4">
          <p className="truncate text-xs text-navy-300">{user?.primaryEmailAddress?.emailAddress}</p>
          <div className="mt-2">
            <UserButton />
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-neutral-200 bg-white px-6">
          <p className="text-sm text-neutral-500">Human-approved actions · nothing sent automatically</p>
          <FictionalBadge />
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
