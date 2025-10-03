# Portfolio Tracker Frontend

A modern, responsive Next.js 14 application for tracking investment portfolio performance.

## Features

- **Dashboard**: Overview of portfolio performance with key metrics, movers, and performance chart
- **Holdings**: Detailed view of all positions with sorting and search
- **Import**: CSV file upload for importing transactions with fee editing
- **Asset Detail**: Individual asset view with position summary, price chart, and transaction history
- **Settings**: Benchmark configuration and manual price refresh

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui (Radix UI primitives)
- **State Management**: TanStack Query (React Query)
- **Charts**: Recharts
- **Icons**: Lucide React
- **HTTP Client**: Axios

## Prerequisites

- Node.js 18+
- Backend API running at http://localhost:8000 (or configured via NEXT_PUBLIC_API_URL)

## Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment variables:
```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Development

Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Build

Build for production:
```bash
npm run build
```

Start production server:
```bash
npm start
```

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js app router pages
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Dashboard page
│   │   ├── providers.tsx       # React Query provider
│   │   ├── holdings/           # Holdings page
│   │   ├── import/             # Import page
│   │   ├── asset/[ticker]/     # Asset detail page
│   │   └── settings/           # Settings page
│   ├── components/             # React components
│   │   ├── ui/                 # shadcn/ui components
│   │   ├── Shared/             # Shared components (Navbar)
│   │   ├── Dashboard/          # Dashboard components
│   │   ├── Import/             # Import components
│   │   ├── Asset/              # Asset detail components
│   │   └── Modals/             # Modal dialogs
│   ├── hooks/                  # Custom React hooks
│   │   ├── usePortfolio.ts     # Portfolio data hooks
│   │   ├── useTransactions.ts  # Transaction hooks
│   │   ├── useAsset.ts         # Asset detail hooks
│   │   ├── useBenchmark.ts     # Benchmark hooks
│   │   ├── usePrices.ts        # Price update hooks
│   │   └── use-toast.ts        # Toast notification hook
│   └── lib/                    # Utility libraries
│       ├── api.ts              # API client
│       ├── types.ts            # TypeScript types
│       └── utils.ts            # Utility functions
├── public/                     # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## Key Features

### Dashboard
- Portfolio overview with 4 key metrics
- Today's top gainers and losers
- Performance chart with time range selector
- Holdings table with sorting

### Import
- Drag-and-drop CSV upload
- Transaction list with fee warnings (⚠️ for missing fees)
- Edit transaction fees via modal

### Asset Detail
- Asset header with current price and 24h change
- Position summary with 6 key metrics
- Price chart with cost basis overlay
- Transaction history

### Settings
- Configure benchmark index
- Manual price refresh
- View last update time

## Design System

### Colors
- Primary: #3B82F6 (Blue)
- Success: #10B981 (Green)
- Danger: #EF4444 (Red)
- Warning: #F59E0B (Amber)
- Background: #F9FAFB (Light Gray)

### Typography
- System fonts (Inter)
- Monospace font for numbers
- Consistent sizing and weights

### Components
All UI components follow shadcn/ui patterns with Tailwind CSS styling.

## API Integration

All API calls are handled through the centralized API client in `src/lib/api.ts`. The application uses TanStack Query for data fetching, caching, and state management.

### Endpoints Used
- `GET /portfolio/overview` - Portfolio metrics
- `GET /portfolio/holdings` - All positions
- `GET /portfolio/performance` - Performance data
- `GET /portfolio/asset/:ticker` - Asset detail
- `POST /transactions/import` - Import CSV
- `GET /transactions/` - List transactions
- `PUT /transactions/:id` - Update transaction
- `GET /benchmark/` - Get benchmark
- `POST /benchmark/` - Set benchmark
- `POST /prices/refresh` - Refresh prices
- `GET /prices/last-update` - Last update time

## Contributing

This is part of the Portfolio Tracker project. See the main project documentation for contribution guidelines.

## License

MIT
