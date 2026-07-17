import React from 'react';
import {
  LayoutDashboard, MessageSquareCode, FileSearch,
  ShieldAlert, Landmark, Brain, History, ChevronLeft, ChevronRight
} from 'lucide-react';
import { User } from '../../types';

interface SidebarProps {
  activePage: string;
  onNavigate: (page: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  user: User | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage, onNavigate, collapsed, onToggleCollapse, user
}) => {
  const initials = (user?.full_name || user?.email || '?')
    .split(/[\s@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part.charAt(0).toUpperCase())
    .join('');
  const categories = [
    {
      title: 'Studio',
      items: [
        { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard }
      ]
    },
    {
      title: 'Intelligence',
      items: [
        { id: 'advisors', label: 'AI Council', icon: MessageSquareCode },
        { id: 'loan', label: 'Loan Intelligence', icon: FileSearch }
      ]
    },
    {
      title: 'Operations',
      items: [
        { id: 'investment', label: 'Investment Portfolio', icon: Landmark },
        { id: 'monitoring', label: 'Continuous Monitor', icon: ShieldAlert }
      ]
    },
    {
      title: 'Advanced Logs',
      items: [
        { id: 'rag', label: 'RAG Explorer', icon: Brain },
        { id: 'decisions', label: 'Decision Replay', icon: History }
      ]
    }
  ];

  return (
    <aside 
      className={`bg-brand-navy text-[#f8fafc] flex flex-col transition-all duration-300 select-none relative ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-white/5">
        <div 
          className="flex items-center gap-3 cursor-pointer"
          onClick={() => onNavigate('landing')}
        >
          <div className="w-8 h-8 rounded bg-[#c09a5f] text-brand-navy font-serif font-bold text-lg flex items-center justify-center">
            P
          </div>
          {!collapsed && (
            <span className="font-serif text-lg font-medium tracking-tight">Prospera</span>
          )}
        </div>
        <button 
          onClick={onToggleCollapse}
          className="text-white/40 hover:text-white p-1 rounded hover:bg-white/5 hidden md:block"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Workspace Switcher */}
      {!collapsed && (
        <div className="p-3 border-b border-white/5">
          <div className="bg-white/5 border border-white/10 rounded-lg p-2.5 flex items-center justify-between cursor-pointer hover:bg-white/10 transition-colors">
            <div className="flex flex-col">
              <span className="text-[10px] text-white/40 font-bold uppercase tracking-wider">Workspace</span>
              <span className="text-xs font-semibold text-white/90">Personal Wealth</span>
            </div>
            <div className="text-[#c09a5f] text-xs">▼</div>
          </div>
        </div>
      )}

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto py-4 space-y-6">
        {categories.map((cat, i) => (
          <div key={i} className="px-3">
            {!collapsed && (
              <span className="text-[9px] font-bold text-white/30 uppercase tracking-widest block mb-2 px-3">
                {cat.title}
              </span>
            )}
            <div className="space-y-1">
              {cat.items.map(item => {
                const isActive = activePage === item.id;
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => onNavigate(item.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                      isActive 
                        ? 'bg-white/10 text-white border-l-2 border-[#c09a5f]' 
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                    title={item.label}
                  >
                    <Icon size={16} className={isActive ? 'text-[#c09a5f]' : ''} />
                    {!collapsed && <span>{item.label}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Footer User Profile */}
      <div className="p-3 border-t border-white/5 bg-black/10">
        <div className="flex items-center gap-3 px-2 py-1.5 cursor-pointer rounded-md hover:bg-white/5" onClick={() => onNavigate('settings')}>
          <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center font-bold text-xs text-[#c09a5f] border border-white/10">
            {initials}
          </div>
          {!collapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="text-xs font-semibold text-white/90 truncate">{user?.full_name || 'Account'}</span>
              <span className="text-[10px] text-white/40 truncate">{user?.email}</span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
