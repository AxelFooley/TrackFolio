'use client';

import { useTheme } from 'next-themes';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function ThemeTestPage() {
  const { theme, resolvedTheme, setTheme } = useTheme();

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <h1 className="text-4xl font-bold">Theme Test Page</h1>
          <ThemeToggle />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Current Theme</CardTitle>
              <CardDescription>The active theme setting</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-mono">{theme}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Resolved Theme</CardTitle>
              <CardDescription>The actual theme being applied</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-mono">{resolvedTheme}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Theme Controls</CardTitle>
              <CardDescription>Manual theme selection</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                variant={theme === 'light' ? 'default' : 'outline'}
                onClick={() => setTheme('light')}
                className="w-full"
              >
                Light
              </Button>
              <Button
                variant={theme === 'dark' ? 'default' : 'outline'}
                onClick={() => setTheme('dark')}
                className="w-full"
              >
                Dark
              </Button>
              <Button
                variant={theme === 'system' ? 'default' : 'outline'}
                onClick={() => setTheme('system')}
                className="w-full"
              >
                System
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <h2 className="text-2xl font-semibold">Color Palette Test</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-primary text-primary-foreground p-4 rounded text-center">
              Primary
            </div>
            <div className="bg-secondary text-secondary-foreground p-4 rounded text-center">
              Secondary
            </div>
            <div className="bg-muted text-muted-foreground p-4 rounded text-center">
              Muted
            </div>
            <div className="bg-accent text-accent-foreground p-4 rounded text-center">
              Accent
            </div>
            <div className="bg-destructive text-destructive-foreground p-4 rounded text-center">
              Destructive
            </div>
            <div className="bg-success text-success-foreground p-4 rounded text-center">
              Success
            </div>
            <div className="bg-warning text-warning-foreground p-4 rounded text-center">
              Warning
            </div>
            <div className="bg-card text-card-foreground p-4 rounded text-center border">
              Card
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <h2 className="text-2xl font-semibold">Typography Test</h2>
          <div className="space-y-2 bg-card p-6 rounded-lg border">
            <h1 className="text-4xl font-bold">Heading 1</h1>
            <h2 className="text-3xl font-semibold">Heading 2</h2>
            <h3 className="text-2xl font-medium">Heading 3</h3>
            <p className="text-lg">This is a large paragraph text that should be readable in both light and dark themes.</p>
            <p className="text-sm text-muted-foreground">This is muted text that should be less prominent.</p>
          </div>
        </div>

        <div className="space-y-4">
          <h2 className="text-2xl font-semibold">Interactive Elements</h2>
          <div className="space-y-4 bg-card p-6 rounded-lg border">
            <div className="flex gap-2 flex-wrap">
              <Button variant="default">Default</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="destructive">Destructive</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}