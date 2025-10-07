# Crypto Paper Portfolio Components

This directory contains components for managing crypto paper portfolios.

## DeletePortfolioModal

A safety-focused modal component for deleting crypto portfolios with multiple confirmation steps to prevent accidental data loss.

### Features

- **Multi-step confirmation process**: Users must type the portfolio name and check acknowledgment box
- **Final warning screen**: Additional confirmation before permanent deletion
- **Clear data loss warnings**: Shows exactly what will be deleted
- **Accessibility features**: Keyboard navigation, proper ARIA labels
- **Loading states**: Prevents duplicate deletions during API calls
- **Error handling**: User-friendly error messages
- **Responsive design**: Works on desktop and mobile

### Props

```typescript
interface DeletePortfolioModalProps {
  isOpen: boolean;                    // Controls modal visibility
  onOpenChange: (open: boolean) => void; // Callback for modal close/open
  portfolio: CryptoPortfolio | null;    // Portfolio to delete
  transactionCount?: number;            // Number of transactions (optional)
  holdingCount?: number;                // Number of holdings (optional)
  onSuccess?: () => void;               // Success callback
  onError?: (error: string) => void;    // Error callback
}
```

### Usage Example

```tsx
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { DeletePortfolioModal } from '@/components/CryptoPaper/DeletePortfolioModal';
import { deleteCryptoPortfolio } from '@/lib/api/crypto-paper';

function PortfolioCard({ portfolio }) {
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [transactionCount] = useState(5); // Fetch from API
  const [holdingCount] = useState(3);     // Fetch from API

  const handleDeleteSuccess = () => {
    // Refresh portfolio list or redirect
    console.log('Portfolio deleted successfully');
  };

  const handleDeleteError = (error: string) => {
    // Show error toast
    console.error('Delete failed:', error);
  };

  return (
    <>
      <Button
        variant="outline"
        onClick={() => setIsDeleteModalOpen(true)}
        className="text-red-600 hover:bg-red-50"
      >
        Delete Portfolio
      </Button>

      <DeletePortfolioModal
        isOpen={isDeleteModalOpen}
        onOpenChange={setIsDeleteModalOpen}
        portfolio={portfolio}
        transactionCount={transactionCount}
        holdingCount={holdingCount}
        onSuccess={handleDeleteSuccess}
        onError={handleDeleteError}
      />
    </>
  );
}
```

### Safety Features

1. **Portfolio Name Confirmation**: Users must type the exact portfolio name
2. **Acknowledgment Checkbox**: Users must confirm they understand the action is irreversible
3. **Final Warning Screen**: Additional confirmation step before deletion
4. **Clear Data Display**: Shows portfolio details and what will be lost
5. **Loading States**: Prevents multiple deletion attempts
6. **Escape Key Support**: Users can press ESC to cancel

### Styling

The component uses Tailwind CSS with the following color scheme:
- **Primary danger**: Red (#EF4444)
- **Warning background**: Red-50 (#FEF2F2)
- **Warning borders**: Red-200 (#FEE2E2)
- **Warning text**: Red-800 (#991B1B)

### Dependencies

- `@radix-ui/react-dialog`: Modal primitives
- `@radix-ui/react-checkbox`: Checkbox component
- `lucide-react`: Icons (AlertTriangle, Wallet, TrendingDown, etc.)
- `@/lib/api/crypto-paper`: API functions
- `@/components/ui/*`: UI components (Button, Input, Label, Checkbox, Alert, Badge)

### API Integration

The component uses the `deleteCryptoPortfolio()` function from the crypto-paper API. Make sure:
- The API endpoint is properly configured
- Error handling is implemented
- Success callbacks refresh the UI appropriately

## Other Components

- `CryptoPortfolioCard.tsx`: Display portfolio information
- `AddTransactionModal.tsx`: Add new transactions
- `EditPortfolioModal.tsx`: Edit portfolio details
- `CryptoHoldingsTable.tsx`: Display portfolio holdings
- `CryptoTransactionTable.tsx`: Display transaction history