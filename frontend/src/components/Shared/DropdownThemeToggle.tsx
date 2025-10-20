'use client';

import React, { useState } from 'react';
import { Moon, Sun, Monitor, Check } from 'lucide-react';
import { useThemeSafe } from '@/hooks/useThemeSafe';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface DropdownThemeToggleProps {
  className?: string;
  variant?: 'default' | 'outline' | 'ghost' | 'secondary';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

export function DropdownThemeToggle({
  className,
  variant = 'ghost',
  size = 'icon',
}: DropdownThemeToggleProps) {
  const [mounted, setMounted] = useState(false);

  // Use theme context safely with fallbacks
  const themeContext = useThemeSafe();
  const { theme, setTheme, isDark, systemTheme } = themeContext;

  React.useEffect(() => {
    setMounted(true);
  }, []);

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

  const getTooltipText = () => {
    switch (theme) {
      case 'light':
        return 'Light theme (click to change)';
      case 'dark':
        return 'Dark theme (click to change)';
      case 'system':
        return 'System theme (click to change)';
      default:
        return 'Theme settings';
    }
  };

  const themeOptions = [
    {
      value: 'light' as const,
      label: 'Light',
      icon: <Sun className="h-4 w-4" />,
      description: 'Use light theme',
    },
    {
      value: 'dark' as const,
      label: 'Dark',
      icon: <Moon className="h-4 w-4" />,
      description: 'Use dark theme',
    },
    {
      value: 'system' as const,
      label: 'System',
      icon: <Monitor className="h-4 w-4" />,
      description: `Follow system preference (${systemTheme === 'dark' ? 'Dark' : 'Light'})`,
    },
  ];

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
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant={variant}
                size={size}
                className={className}
                aria-label={getTooltipText()}
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
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {themeOptions.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  onClick={() => setTheme(option.value)}
                  className="flex items-center justify-between cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 flex items-center justify-center">
                      {option.icon}
                    </span>
                    <div>
                      <div className="font-medium">{option.label}</div>
                      <div className="text-xs text-muted-foreground">
                        {option.description}
                      </div>
                    </div>
                  </div>
                  {theme === option.value && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </TooltipTrigger>
        <TooltipContent>
          <p>{getTooltipText()}</p>
          <p className="text-xs opacity-75 mt-1">
            Current: {theme === 'light' ? 'Light' : theme === 'dark' ? 'Dark' : 'System'} {theme === 'system' && `(${isDark ? 'Dark' : 'Light'})`}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// Standalone dropdown theme toggle with integrated tooltip provider
export function DropdownThemeToggleWithTooltip(props: DropdownThemeToggleProps) {
  return (
    <TooltipProvider>
      <DropdownThemeToggle {...props} />
    </TooltipProvider>
  );
}