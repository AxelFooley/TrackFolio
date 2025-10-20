"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./card"
import { Badge } from "./badge"
import { Button } from "./button"

export function ThemeDemo() {
  return (
    <div className="p-6 space-y-6 max-w-2xl mx-auto">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Dark Mode Demo</h1>
        <p className="text-muted-foreground">
          This demonstrates the comprehensive dark mode CSS variables system.
        </p>
      </div>

      {/* Status Colors */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-success rounded-full mx-auto mb-2" />
            <p className="text-sm font-medium">Success</p>
            <Badge variant="secondary" className="mt-2">
              Active
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-warning rounded-full mx-auto mb-2" />
            <p className="text-sm font-medium">Warning</p>
            <Badge variant="outline" className="mt-2">
              Pending
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-destructive rounded-full mx-auto mb-2" />
            <p className="text-sm font-medium">Danger</p>
            <Badge variant="destructive" className="mt-2">
              Error
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-info rounded-full mx-auto mb-2" />
            <p className="text-sm font-medium">Info</p>
            <Badge className="mt-2">
              Info
            </Badge>
          </CardContent>
        </Card>
      </div>

      {/* Chart Colors */}
      <Card>
        <CardHeader>
          <CardTitle>Chart Colors</CardTitle>
          <CardDescription>
            Optimized colors for data visualization in both themes
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((num) => (
              <div key={num} className="text-center">
                <div
                  className="w-12 h-12 rounded-lg mx-auto mb-1"
                  style={{ backgroundColor: `hsl(var(--chart-${num}))` }}
                />
                <p className="text-xs text-muted-foreground">{num}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Interactive Elements */}
      <Card>
        <CardHeader>
          <CardTitle>Interactive Elements</CardTitle>
          <CardDescription>
            Test different states and transitions
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button>Primary Button</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
          </div>

          <div className="p-4 border rounded-lg bg-muted">
            <p className="text-muted-foreground">
              This is a muted background section with muted text color.
              Notice how it adapts to both light and dark themes.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Border Variations */}
      <Card className="border-2">
        <CardHeader>
          <CardTitle>Border Examples</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 border border-border rounded-lg">
              <p className="text-sm">Default Border</p>
            </div>
            <div className="p-4 border-2 border-primary rounded-lg">
              <p className="text-sm">Primary Border</p>
            </div>
            <div className="p-4 border-dashed border-muted-foreground rounded-lg">
              <p className="text-sm">Dashed Border</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}