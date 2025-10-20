# Dark Mode Implementation Guide

This guide explains how to use the comprehensive dark mode CSS variables system implemented in TrackFolio.

## Overview

The dark mode implementation includes:
- **Comprehensive CSS variables** following shadcn/ui patterns
- **Smooth transitions** for theme switching
- **Chart colors** optimized for both themes
- **Accessibility-focused** contrast ratios
- **System preference detection**

## Available CSS Variables

### Base Colors
```css
/* Backgrounds */
--background
--foreground
--card
--card-foreground
--popover
--popover-foreground

/* Semantic Colors */
--primary
--primary-foreground
--secondary
--secondary-foreground
--muted
--muted-foreground
--accent
--accent-foreground

/* Status Colors */
--destructive
--destructive-foreground
--success
--success-foreground
--danger
--danger-foreground
--warning
--warning-foreground
--info
--info-foreground

/* UI Elements */
--border
--input
--ring
--ghost
--ghost-foreground
```

### Chart Colors
```css
--chart-1: /* Red */
--chart-2: /* Green */
--chart-3: /* Blue */
--chart-4: /* Yellow */
--chart-5: /* Orange */
--chart-6: /* Purple */
--chart-7: /* Red variant */
--chart-8: /* Green variant */
```

## Usage Examples

### 1. Using CSS Variables in Components

```tsx
// Direct CSS variable usage
<div className="bg-card text-card-foreground border-border rounded-lg p-4">
  <h2 className="text-primary text-xl font-semibold">Card Title</h2>
  <p className="text-muted-foreground">Card content goes here</p>
</div>
```

### 2. Chart Implementation

```tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

function PerformanceChart() {
  return (
    <div className="bg-card rounded-lg p-6 border">
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis stroke="hsl(var(--muted-foreground))" />
        <YAxis stroke="hsl(var(--muted-foreground))" />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            color: 'hsl(var(--card-foreground))'
          }}
        />
        <Line type="monotone" dataKey="value" stroke="hsl(var(--chart-1))" />
      </LineChart>
    </div>
  );
}
```

### 3. Status Indicators

```tsx
function StatusBadge({ status }: { status: 'success' | 'warning' | 'error' }) {
  const statusColors = {
    success: 'bg-success text-success-foreground',
    warning: 'bg-warning text-warning-foreground',
    error: 'bg-destructive text-destructive-foreground'
  };

  return (
    <Badge className={statusColors[status]}>
      {status}
    </Badge>
  );
}
```

### 4. Custom Component with Dark Mode Support

```tsx
function CustomCard({ children, className }: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-sm",
        "transition-all duration-200 hover:shadow-md",
        "hover:bg-accent/50 hover:text-accent-foreground",
        className
      )}
    >
      {children}
    </div>
  );
}
```

## Theme Toggle Component

Use the provided `ThemeToggle` component in your UI:

```tsx
import { ThemeToggle } from '@/components/ui/theme-toggle';

function YourComponent() {
  return (
    <div className="flex items-center justify-between">
      <h1>Your App</h1>
      <ThemeToggle />
    </div>
  );
}
```

## Programmatic Theme Control

Access theme programmatically using `next-themes`:

```tsx
import { useTheme } from 'next-themes';

function ThemeController() {
  const { theme, setTheme, systemTheme, resolvedTheme } = useTheme();

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  return (
    <div>
      <p>Current theme: {resolvedTheme}</p>
      <button onClick={toggleTheme}>Toggle Theme</button>
    </div>
  );
}
```

## Transition Effects

The implementation includes smooth transitions:

- **Global transitions**: 0.3s ease for colors, borders, backgrounds
- **Interactive elements**: 0.2s ease for buttons, inputs
- **Chart elements**: 0.3s ease for data visualizations

## Custom Colors

To add custom colors, extend the CSS variables:

```css
:root {
  --custom-color: 210 40% 50%;
  --custom-color-foreground: 210 40% 98%;
}

.dark {
  --custom-color: 210 40% 30%;
  --custom-color-foreground: 210 40% 95%;
}
```

Then use in Tailwind:

```tsx
<div className="bg-[hsl(var(--custom-color))] text-[hsl(var(--custom-color-foreground))]">
  Custom styled content
</div>
```

## Best Practices

1. **Use semantic variables**: Prefer `primary`, `secondary`, `muted` over hardcoded colors
2. **Ensure accessibility**: Dark mode colors maintain WCAG AA contrast ratios
3. **Test both themes**: Always verify components work in both light and dark modes
4. **Consider system preference**: The theme automatically respects user's OS preference
5. **Smooth transitions**: Components automatically transition when theme changes

## Migration Guide

To migrate existing components:

1. Replace hardcoded colors with CSS variables
2. Update Tailwind classes to use semantic color names
3. Test in both light and dark modes
4. Add transitions where appropriate

### Before
```tsx
<div className="bg-white text-gray-900 border-gray-200">
  <button className="bg-blue-500 text-white hover:bg-blue-600">
    Button
  </button>
</div>
```

### After
```tsx
<div className="bg-card text-card-foreground border-border">
  <button className="bg-primary text-primary-foreground hover:bg-primary/90">
    Button
  </button>
</div>
```

## Troubleshooting

### Theme Not Applying
- Ensure `ThemeProvider` wraps your app
- Check `next-themes` dependency is installed
- Verify CSS variables are properly defined

### Flickering on Load
- The `disableTransitionOnChange` prop prevents FOUC
- Theme detection happens before rendering

### Colors Not Updating
- Clear browser cache
- Check CSS specificity
- Verify Tailwind build includes new variables