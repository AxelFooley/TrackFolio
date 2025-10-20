'use client';

import React, { useState } from 'react';
import { Moon, Sun, Monitor } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
  variant?: 'default' | 'outline' | 'ghost' | 'secondary';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

export function ThemeToggle({
  className,
  showLabel = false,
  variant = 'ghost',
  size = 'icon',
}: ThemeToggleProps) {
  const [mounted, setMounted] = useState(false);

  // Try to get theme context, but handle errors gracefully
  let theme: 'light' | 'dark' | 'system' = 'light';
  let setTheme: (theme: 'light' | 'dark' | 'system') => void = () => {};
  let isDark = false;

  try {
    const themeContext = useTheme();
    theme = themeContext.theme;
    setTheme = themeContext.setTheme;
    isDark = themeContext.isDark;
  } catch (error) {
    // Theme context not available (likely during SSR)
    // Use default values
    console.warn('Theme context not available');
  }

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const cycleTheme = () => {
    const themeOrder: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system'];
    const currentIndex = themeOrder.indexOf(theme as 'light' | 'dark' | 'system');
    const nextIndex = (currentIndex + 1) % themeOrder.length;
    setTheme(themeOrder[nextIndex]);
  };

  const getThemeIcon = () => {
    switch (theme) {
      case 'light':
        return <Sun className="h-[1.2rem] w-[1.2rem]" />;
      case 'dark':
        return <Moon className="h-[1.2rem] w-[1.2rem]" />;
      case 'system':
        return <Monitor className="h-[1.2rem] w-[1.2rem]" />;
      default:
        return <Sun className="h-[1.2rem] w-[1.2rem]" />;
    }
  };

  const getThemeLabel = () => {
    switch (theme) {
      case 'light':
        return 'Light';
      case 'dark':
        return 'Dark';
      case 'system':
        return 'System';
      default:
        return 'Light';
    }
  };

  const getTooltipText = () => {
    switch (theme) {
      case 'light':
        return 'Switch to Dark theme';
      case 'dark':
        return 'Switch to System theme';
      case 'system':
        return 'Switch to Light theme';
      default:
        return 'Switch theme';
    }
  };

  // Prevent hydration mismatch by not rendering until mounted
  if (!mounted) {
    return (
      <Button
        variant={variant}
        size={size}
        className={className}
        disabled
        aria-hidden="true"
      >
        <Sun className="h-[1.2rem] w-[1.2rem]" />
      </Button>
    );
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant={variant}
            size={size}
            onClick={cycleTheme}
            className={className}
            aria-label={getTooltipText()}
            title={getTooltipText()}
          >
            <span className="relative flex items-center justify-center">
              <span
                className={`
                  transition-all duration-300 ease-in-out
                  ${theme === 'light' ? 'rotate-0 scale-100 opacity-100' : 'rotate-90 scale-0 opacity-0 absolute'}
                `}
              >
                <Sun className="h-[1.2rem] w-[1.2rem]" />
              </span>
              <span
                className={`
                  transition-all duration-300 ease-in-out
                  ${theme === 'dark' ? 'rotate-0 scale-100 opacity-100' : '-rotate-90 scale-0 opacity-0 absolute'}
                `}
              >
                <Moon className="h-[1.2rem] w-[1.2rem]" />
              </span>
              <span
                className={`
                  transition-all duration-300 ease-in-out
                  ${theme === 'system' ? 'rotate-0 scale-100 opacity-100' : 'rotate-180 scale-0 opacity-0 absolute'}
                `}
              >
                <Monitor className="h-[1.2rem] w-[1.2rem]" />
              </span>
            </span>
            {showLabel && (
              <span className="ml-2 text-sm font-medium">
                {getThemeLabel()}
              </span>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{getTooltipText()}</p>
          <p className="text-xs opacity-75 mt-1">
            Current: {getThemeLabel()} {theme === 'system' && `(${isDark ? 'Dark' : 'Light'})`}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// Standalone theme toggle with integrated tooltip provider
export function ThemeToggleWithTooltip(props: ThemeToggleProps) {
  return (
    <TooltipProvider>
      <ThemeToggle {...props} />
    </TooltipProvider>
  );
}

// Compact version for mobile or tight spaces
export function CompactThemeToggle({ className }: { className?: string }) {
  const [mounted, setMounted] = React.useState(false);

  // Try to get theme context, but handle errors gracefully
  let theme: 'light' | 'dark' | 'system' = 'light';
  let setTheme: (theme: 'light' | 'dark' | 'system') => void = () => {};

  try {
    const themeContext = useTheme();
    theme = themeContext.theme;
    setTheme = themeContext.setTheme;
  } catch (error) {
    // Theme context not available (likely during SSR)
    console.warn('Theme context not available');
  }

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className={className}
        disabled
        aria-hidden="true"
      >
        <Sun className="h-5 w-5" />
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      className={className}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
    >
      <div className="relative w-5 h-5">
        <Sun
          className={`
            absolute inset-0 h-5 w-5 transition-all duration-300
            ${theme === 'light' ? 'rotate-0 scale-100 opacity-100' : 'rotate-90 scale-0 opacity-0'}
          `}
        />
        <Moon
          className={`
            absolute inset-0 h-5 w-5 transition-all duration-300
            ${theme === 'dark' ? 'rotate-0 scale-100 opacity-100' : '-rotate-90 scale-0 opacity-0'}
          `}
        />
      </div>
    </Button>
  );
}

// Advanced theme selector with all three options visible
export function ThemeSelector({ className }: { className?: string }) {
  const [mounted, setMounted] = React.useState(false);

  // Try to get theme context, but handle errors gracefully
  let theme: 'light' | 'dark' | 'system' = 'light';
  let setTheme: (theme: 'light' | 'dark' | 'system') => void = () => {};

  try {
    const themeContext = useTheme();
    theme = themeContext.theme;
    setTheme = themeContext.setTheme;
  } catch (error) {
    // Theme context not available (likely during SSR)
    console.warn('Theme context not available');
  }

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const themes: Array<{ value: 'light' | 'dark' | 'system'; label: string; icon: React.ReactNode }> = [
    {
      value: 'light',
      label: 'Light',
      icon: <Sun className="h-4 w-4" />,
    },
    {
      value: 'dark',
      label: 'Dark',
      icon: <Moon className="h-4 w-4" />,
    },
    {
      value: 'system',
      label: 'System',
      icon: <Monitor className="h-4 w-4" />,
    },
  ];

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <div className={`flex items-center gap-1 p-1 rounded-lg border bg-muted ${className}`}>
        {themes.map((t) => (
          <Button
            key={t.value}
            variant="ghost"
            size="sm"
            disabled
            className="flex items-center gap-2 h-8"
            aria-hidden="true"
          >
            {t.icon}
            <span className="hidden sm:inline">{t.label}</span>
          </Button>
        ))}
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-1 p-1 rounded-lg border bg-muted ${className}`}>
      {themes.map((t) => (
        <Button
          key={t.value}
          variant={theme === t.value ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTheme(t.value)}
          className="flex items-center gap-2 h-8"
          aria-label={`Set theme to ${t.label}`}
        >
          {t.icon}
          <span className="hidden sm:inline">{t.label}</span>
        </Button>
      ))}
    </div>
  );
}