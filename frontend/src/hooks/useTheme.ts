import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'bankwise-theme';

/**
 * Determine the correct initial theme AND apply it to the document
 * element synchronously — this runs during useState initialisation,
 * which happens before React's first render, eliminating the flash of
 * wrong theme that the async useEffect approach causes on Render.
 */
function getInitialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  const theme: Theme =
    stored === 'light' || stored === 'dark'
      ? stored
      : window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';

  // Apply immediately so the very first paint already has the right class.
  document.documentElement.classList.toggle('dark', theme === 'dark');
  return theme;
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    // Keeps the class in sync for every subsequent toggle and persists
    // the user's explicit choice so it survives page refreshes / new tabs.
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'));

  return { theme, toggleTheme };
}
