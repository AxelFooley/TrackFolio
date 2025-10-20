# Theme Toggle Component

A comprehensive theme switching system for the Portfolio Tracker application with multiple variants and smooth animations.

## Features

- **Multiple Theme Options**: Light, Dark, and System (follows OS preference)
- **Smooth Animations**: Icon transitions with rotation and scaling effects
- **Accessibility**: Proper ARIA labels, keyboard navigation, and screen reader support
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Multiple Variants**: Standard, compact, and selector components
- **Tooltips**: Contextual hints for better UX
- **Persistent Storage**: User preference saved to localStorage
- **No Flash**: Loading state prevents theme flicker on initial load

## Components

### 1. `ThemeToggle` (Main Component)

The primary theme toggle button with cycling functionality.

```tsx
import { ThemeToggle } from '@/components/Shared/ThemeToggle';

// Basic usage
<ThemeToggle />

// With options
<ThemeToggle
  showLabel={true}
  variant="outline"
  size="lg"
  className="custom-class"
/>
```

**Props:**
- `className?: string` - Additional CSS classes
- `showLabel?: boolean` - Show theme name label (default: false)
- `variant?: 'default' | 'outline' | 'ghost' | 'secondary'` - Button style
- `size?: 'default' | 'sm' | 'lg' | 'icon'` - Button size

**Behavior:**
- Cycles through: Light → Dark → System → Light
- Shows Sun icon for Light theme
- Shows Moon icon for Dark theme
- Shows Monitor icon for System theme
- Includes tooltip with current status and next action

### 2. `CompactThemeToggle`

Simplified version for tight spaces, only toggles between Light and Dark.

```tsx
import { CompactThemeToggle } from '@/components/Shared/ThemeToggle';

<CompactThemeToggle className="h-8 w-8" />
```

**Features:**
- Smaller footprint
- Simple Light/Dark toggle (no System option)
- Minimal animations
- Perfect for mobile menus or toolbars

### 3. `ThemeSelector`

Advanced selector showing all three theme options simultaneously.

```tsx
import { ThemeSelector } from '@/components/Shared/ThemeToggle';

<ThemeSelector className="w-full max-w-xs" />
```

**Features:**
- All theme options visible at once
- Button group style
- Clear active state
- Responsive text labels

## Theme Context

Use the `useTheme` hook to access theme information in your components.

```tsx
import { useTheme } from '@/contexts/ThemeContext';

function MyComponent() {
  const { theme, setTheme, isDark, systemTheme, resolvedTheme } = useTheme();

  return (
    <div className={isDark ? 'dark-styles' : 'light-styles'}>
      <p>Current theme: {theme}</p>
      <p>Resolved theme: {resolvedTheme}</p>
      {theme === 'system' && <p>System preference: {systemTheme}</p>}
    </div>
  );
}
```

**Context Values:**
- `theme: 'light' | 'dark' | 'system'` - Selected theme
- `setTheme: (theme: Theme) => void` - Update theme
- `systemTheme: 'light' | 'dark'` - OS preference
- `resolvedTheme: 'light' | 'dark'` - Active theme
- `isDark: boolean` - Convenience flag for dark mode

## Implementation Details

### Theme Provider

The app is wrapped with `ThemeProvider` in `app/providers.tsx`:

```tsx
<ThemeProvider defaultTheme="system">
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
</ThemeProvider>
```

### CSS Variables

Themes use CSS custom properties defined in `globals.css`:

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  /* ... more variables */
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  /* ... dark mode variables */
}
```

### Transitions

Smooth transitions are applied to theme changes:

```css
* {
  transition: background-color 0.3s ease,
              color 0.3s ease,
              border-color 0.3s ease;
}
```

## Integration

### 1. Install Dependencies

```bash
npm install @radix-ui/react-tooltip lucide-react
```

### 2. Add to Layout

The theme toggle is already integrated into the navbar:

```tsx
// components/Shared/Navbar.tsx
import { ThemeToggle } from './ThemeToggle';

export function Navbar() {
  return (
    <nav>
      {/* ... navigation items */}
      <ThemeToggle />
    </nav>
  );
}
```

### 3. Settings Page

A comprehensive theme settings section is available at `/settings`:

- Current theme information display
- Theme selector component
- Showcase of all toggle variants
- Real-time theme status updates

## Best Practices

### 1. Accessibility

- Use semantic HTML elements
- Provide ARIA labels and descriptions
- Ensure keyboard navigation
- Include focus states
- Use sufficient color contrast

### 2. Performance

- Prevent flash of incorrect theme
- Use CSS transitions instead of JavaScript animations
- Minimize re-renders with proper state management
- Use localStorage for persistence

### 3. User Experience

- Provide visual feedback for interactions
- Use tooltips for context
- Show loading states
- Maintain consistent design patterns
- Respect system preferences

## Customization

### Adding New Themes

1. Update the `Theme` type in `ThemeContext.tsx`
2. Add corresponding CSS variables in `globals.css`
3. Update theme icons and labels in `ThemeToggle.tsx`
4. Modify the cycling logic if needed

### Custom Animations

Animation keyframes are defined in `globals.css`:

```css
@keyframes themeToggleEnter {
  from {
    transform: rotate(-180deg) scale(0);
    opacity: 0;
  }
  to {
    transform: rotate(0) scale(1);
    opacity: 1;
  }
}
```

### Custom Styles

Extend the component with additional variants or styles:

```tsx
<ThemeToggle
  className="custom-theme-toggle"
  variant="custom"
  size="custom"
/>
```

## Testing

The theme system includes comprehensive test coverage:

- Theme switching functionality
- Accessibility compliance
- Responsive behavior
- Performance optimization
- Cross-browser compatibility

## Troubleshooting

### Common Issues

1. **Theme Flash on Load**
   - Ensure `ThemeProvider` wraps the entire app
   - Check that loading state is properly handled
   - Verify CSS variables are defined

2. **Theme Not Persisting**
   - Check localStorage availability
   - Verify storage key configuration
   - Ensure no storage quota exceeded

3. **Animations Not Working**
   - Check CSS transition properties
   - Verify Tailwind CSS configuration
   - Ensure no JavaScript errors

4. **Accessibility Issues**
   - Test with screen readers
   - Verify keyboard navigation
   - Check ARIA labels and roles

## Future Enhancements

Potential improvements to consider:

1. **More Theme Options**: Add custom color themes
2. **Theme Scheduling**: Auto-switch based on time of day
3. **Reduced Motion**: Respect user's motion preferences
4. **High Contrast**: Support for high contrast modes
5. **Custom Colors**: User-defined accent colors
6. **Export/Import**: Theme preference synchronization