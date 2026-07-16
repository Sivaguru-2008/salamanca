import React from 'react';
import { Search, Bell, Settings, LogOut } from 'lucide-react';
import { User } from '../../types';

interface HeaderProps {
  activePage: string;
  onOpenCommand: () => void;
  onNavigate: (page: string) => void;
  apiOnline: boolean;
  user: User | null;
  onLogout: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activePage, onOpenCommand, onNavigate, apiOnline, user, onLogout
}) => {
  const getBreadcrumbs = () => {
    const formatted = activePage.charAt(0).toUpperCase() + activePage.slice(1);
    return ['FIOS', formatted];
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <header className="h-16 border-b border-black/5 bg-[#faf8f5]/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-40 select-none">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs font-medium text-brand-graphite/40">
        {breadcrumbs.map((crumb, idx) => (
          <React.Fragment key={idx}>
            {idx > 0 && <span>/</span>}
            <span className={idx === breadcrumbs.length - 1 ? 'text-brand-graphite font-semibold' : ''}>
              {crumb}
            </span>
          </React.Fragment>
        ))}
      </div>

      {/* Center Search Input Trigger */}
      <div
        className="w-80 max-w-md bg-white border border-black/5 rounded-full px-4 py-1.5 flex items-center gap-3 cursor-pointer text-brand-graphite/30 hover:border-[#c09a5f]/40 transition-colors"
        onClick={onOpenCommand}
      >
        <Search size={14} />
        <span className="text-xs flex-1">Search or ask advisor...</span>
        <kbd className="text-[10px] bg-black/5 px-1.5 py-0.5 rounded border border-black/5 font-sans font-bold">
          Ctrl K
        </kbd>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-5">
        {/* Live backend status pill */}
        <div className="flex items-center gap-2 bg-white border border-black/5 px-3 py-1.5 rounded-full shadow-subtle">
          <span className={`w-2 h-2 rounded-full ${apiOnline ? 'bg-green-500 shadow-md shadow-green-500/20' : 'bg-red-500 animate-pulse'}`}></span>
          <span className="text-[11px] font-bold text-brand-graphite/60">
            {apiOnline ? 'Backend Connected' : 'Backend Offline'}
          </span>
        </div>

        {/* Notifications */}
        <button
          className="relative text-brand-graphite/60 hover:text-brand-graphite p-1 rounded-full hover:bg-black/5"
          onClick={() => onNavigate('monitoring')}
        >
          <Bell size={18} />
        </button>

        {/* Settings Shortcut */}
        <button
          className="text-brand-graphite/60 hover:text-brand-graphite p-1 rounded-full hover:bg-black/5"
          onClick={() => onNavigate('settings')}
        >
          <Settings size={18} />
        </button>

        {/* User + Logout */}
        <div className="flex items-center gap-3 border-l border-black/5 pl-4">
          <div className="w-8 h-8 rounded-full bg-[#0a1120] text-white flex items-center justify-center text-xs font-bold uppercase">
            {(user?.full_name || user?.email || '?').charAt(0)}
          </div>
          <div className="hidden md:flex flex-col leading-tight max-w-[140px]">
            <span className="text-[11px] font-semibold text-brand-navy truncate">
              {user?.full_name || 'Account'}
            </span>
            <span className="text-[9px] text-brand-graphite/40 truncate">{user?.email}</span>
          </div>
          <button
            onClick={onLogout}
            title="Sign out"
            className="text-brand-graphite/60 hover:text-red-500 p-1 rounded-full hover:bg-black/5"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </header>
  );
};
