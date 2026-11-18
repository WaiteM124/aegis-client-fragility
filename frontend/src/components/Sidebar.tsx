import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Globe, ShieldCheck, Plus } from 'lucide-react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/events', label: 'Events', icon: Globe },
  { to: '/assessments', label: 'Assessments', icon: ShieldCheck },
  { to: '/submit', label: 'Submit Event', icon: Plus },
];

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-full w-[220px] bg-slate-900 border-r border-slate-700/50 flex flex-col z-20">
      {/* Logo */}
      <div className="px-5 pt-6 pb-4">
        <div
          className="font-mono text-cyan-400 text-xl font-bold tracking-widest"
          style={{ textShadow: '0 0 8px rgba(34,211,238,0.6)' }}
        >
          AEGIS
        </div>
        <div className="text-[10px] text-slate-500 tracking-widest mt-0.5">
          GLOBAL INTELLIGENCE
        </div>
      </div>

      {/* Divider */}
      <div className="mx-4 border-t border-slate-700/50" />

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-slate-700/50 text-white border-l-2 border-cyan-400 pl-[10px]'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50 border-l-2 border-transparent pl-[10px]'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-700/50">
        <p className="text-[10px] text-slate-600 tracking-wide">© 2026 Aegis</p>
      </div>
    </aside>
  );
}
