import React, { useState } from 'react';
import { Search, Sun, Moon, Bell, ChevronDown, Check } from 'lucide-react';

interface HeaderProps {
  userName?: string;
  onSearchChange?: (val: string) => void;
  onOpenNotifications?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  userName = 'John',
  onSearchChange,
}) => {
  const [searchVal, setSearchVal] = useState('');
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [hasNotifications, setHasNotifications] = useState(true);
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchVal(e.target.value);
    if (onSearchChange) onSearchChange(e.target.value);
  };

  return (
    <header className="h-16 border-b border-stone-800/60 bg-[#16171d] px-6 flex items-center justify-between shrink-0 select-none">
      {/* Left: User Welcome Greeting */}
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight">
          Hi, <span className="text-purple-400">{userName}!</span>
        </h1>
      </div>

      {/* Center: Search Input Bar */}
      <div className="relative w-72 md:w-96">
        <Search className="w-4 h-4 text-stone-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={searchVal}
          onChange={handleSearch}
          placeholder="Search Something..."
          className="w-full bg-[#1e2029] border border-stone-800/80 rounded-full pl-10 pr-4 py-2 text-xs font-medium text-stone-200 placeholder-stone-500 focus:outline-none focus:border-purple-500/50 transition-all"
        />
      </div>

      {/* Right: Theme Toggle, Notifications, User Avatar Dropdown */}
      <div className="flex items-center space-x-4">
        {/* Day / Night Theme Toggle Switch */}
        <button
          onClick={() => setIsDarkMode(!isDarkMode)}
          className="flex items-center space-x-1.5 bg-[#1e2029] border border-stone-800/80 p-1.5 rounded-full text-stone-400 hover:text-stone-200 transition-colors cursor-pointer"
          title="Toggle Visual Mode"
        >
          <div className={`p-1 rounded-full ${isDarkMode ? 'text-stone-500' : 'bg-amber-400 text-stone-900'}`}>
            <Sun className="w-3.5 h-3.5" />
          </div>
          <div className={`p-1 rounded-full ${isDarkMode ? 'bg-purple-600 text-white' : 'text-stone-500'}`}>
            <Moon className="w-3.5 h-3.5" />
          </div>
        </button>

        {/* Notifications Bell Icon */}
        <button
          onClick={() => setHasNotifications(false)}
          className="relative p-2 bg-[#1e2029] border border-stone-800/80 rounded-full text-stone-300 hover:text-white transition-colors cursor-pointer"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
          {hasNotifications && (
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-pink-500 ring-2 ring-[#16171d]" />
          )}
        </button>

        {/* User Profile Avatar Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            className="flex items-center space-x-2.5 bg-[#1e2029] hover:bg-stone-800 border border-stone-800/80 rounded-full pl-1.5 pr-3 py-1 transition-colors cursor-pointer"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-purple-500 to-pink-500 flex items-center justify-center font-bold text-xs text-white overflow-hidden">
              <img
                src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=120"
                alt="Avatar"
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <span>J</span>
            </div>
            <span className="text-xs font-semibold text-stone-200">{userName}</span>
            <ChevronDown className="w-3.5 h-3.5 text-stone-400" />
          </button>

          {showProfileMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-[#1e2029] border border-stone-800 rounded-xl shadow-xl py-2 z-50 text-xs text-stone-300">
              <div className="px-3 py-1.5 border-b border-stone-800 text-stone-400">
                Logged in as <span className="text-white font-bold">{userName}</span>
              </div>
              <div className="px-3 py-1.5 hover:bg-stone-800 cursor-pointer">Account Settings</div>
              <div className="px-3 py-1.5 hover:bg-stone-800 cursor-pointer">API Keys</div>
              <div className="px-3 py-1.5 text-rose-400 hover:bg-rose-500/10 cursor-pointer">Log out</div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
