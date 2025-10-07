'use client';

import { EditPortfolioModal } from './EditPortfolioModal';
import type { CryptoPortfolio } from '@/types/crypto-paper';

interface EditPortfolioExampleProps {
  portfolio: CryptoPortfolio;
  onPortfolioUpdated: () => void;
}

/**
 * Example usage of EditPortfolioModal component
 *
 * This shows how to integrate the EditPortfolioModal into your existing components.
 * You can customize the trigger button or use the default one.
 */
export function EditPortfolioExample({ portfolio, onPortfolioUpdated }: EditPortfolioExampleProps) {
  return (
    <div className="flex gap-2">
      {/* Usage with default trigger */}
      <EditPortfolioModal
        portfolio={portfolio}
        onPortfolioUpdated={onPortfolioUpdated}
      />

      {/* Usage with custom trigger */}
      <EditPortfolioModal
        portfolio={portfolio}
        onPortfolioUpdated={onPortfolioUpdated}
        trigger={
          <button className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600">
            Edit Portfolio
          </button>
        }
      />
    </div>
  );
}

/**
 * Integration example in a portfolio card component:
 *
 * ```tsx
 * import { EditPortfolioModal } from './EditPortfolioModal';
 *
 * function PortfolioCard({ portfolio }: { portfolio: CryptoPortfolio }) {
 *   const [portfolios, setPortfolios] = useState<CryptoPortfolio[]>([]);
 *
 *   const handlePortfolioUpdated = () => {
 *     // Refresh portfolio list or update local state
 *     refreshPortfolios();
 *   };
 *
 *   return (
 *     <div className="p-4 border rounded-lg">
 *       <div className="flex justify-between items-start">
 *         <div>
 *           <h3 className="font-semibold">{portfolio.name}</h3>
 *           <p className="text-sm text-gray-600">{portfolio.description}</p>
 *         </div>
 *         <EditPortfolioModal
 *           portfolio={portfolio}
 *           onPortfolioUpdated={handlePortfolioUpdated}
 *         />
 *       </div>
 *     </div>
 *   );
 * }
 * ```
 */