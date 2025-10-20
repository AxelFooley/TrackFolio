'use client';

import { useTheme } from '@/contexts/ThemeContext';

export function useThemeSafe() {
  try {
    return useTheme();
  } catch (error) {
    // Theme context not available - return default values
    // This can happen during SSR or when ThemeProvider is not wrapped
    return {
      theme: 'system' as const,
      setTheme: () => {},
      systemTheme: 'light' as const,
      resolvedTheme: 'light' as const,
      isDark: false,
    };
  }
}