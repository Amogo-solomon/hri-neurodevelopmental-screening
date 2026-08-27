'use client';
import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  // Avoid hydration mismatch — next-themes only knows the real theme
  // after mount (it reads localStorage on the client).
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div className="w-9 h-9 rounded-lg" aria-hidden />;
  }

  const isLight = theme === 'light';

  return (
    <button
      onClick={() => setTheme(isLight ? 'dark' : 'light')}
      className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0
                 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50
                 transition-colors"
      title={isLight ? 'Switch to night mode' : 'Switch to day mode'}
      aria-label={isLight ? 'Switch to night mode' : 'Switch to day mode'}
    >
      {isLight
        ? <Moon className="w-4 h-4 text-slate-300" />
        : <Sun  className="w-4 h-4 text-amber-300" />}
    </button>
  );
}