'use client';

import { useState, useEffect, useMemo } from 'react';
import { Check, ChevronsUpDown, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { searchTickers, type TickerSearchResult } from '@/lib/api';

interface TickerAutocompleteProps {
  value: string;
  onSelect: (ticker: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function TickerAutocomplete({
  value,
  onSelect,
  placeholder = 'Search by company name or ticker symbol...',
  disabled = false,
}: TickerAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Highlight matching text in results
  const highlightMatch = useMemo(() => {
    return (text: string) => {
      if (!searchQuery || !text) return text;

      const regex = new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
      const parts = text.split(regex);
      const escapedQuery = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

      return parts.map((part, index) =>
        new RegExp(escapedQuery, 'i').test(part) ? (
          <span key={index} className="font-semibold text-blue-600">{part}</span>
        ) : (
          <span key={index}>{part}</span>
        )
      );
    };
  }, [searchQuery]);

  // Debounce search
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 1) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      setHasError(false);
      try {
        const data = await searchTickers(searchQuery);
        setResults(data);
      } catch (error) {
        console.error('Error searching tickers:', error);
        setResults([]);
        setHasError(true);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load initial suggestions when opening
  useEffect(() => {
    if (open && results.length === 0 && !searchQuery) {
      // Load common benchmarks when opening
      searchTickers('s&p').then(setResults).catch(console.error);
    }
  }, [open]);

  const handleSelect = (ticker: string) => {
    onSelect(ticker);
    setOpen(false);
    setSearchQuery('');
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          {value || placeholder}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[450px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search by company name (e.g., Apple, Microsoft) or ticker (e.g., AAPL, MSFT)..."
            value={searchQuery}
            onValueChange={setSearchQuery}
          />
          <CommandList>
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-6 text-sm text-gray-500">
                <Loader2 className="h-5 w-5 animate-spin text-gray-400 mb-2" />
                Searching...
              </div>
            ) : hasError ? (
              <div className="flex flex-col items-center justify-center py-6 text-sm text-red-500">
                <AlertCircle className="h-5 w-5 mb-2" />
                <div className="text-center px-4">
                  Search failed. Please check your connection and try again.
                </div>
              </div>
            ) : results.length === 0 ? (
              <CommandEmpty>
                {searchQuery
                  ? 'No results found. Try searching with different company names or ticker symbols.'
                  : 'Search for stocks, ETFs, indices, and more by company name or ticker symbol.'}
              </CommandEmpty>
            ) : (
              <CommandGroup>
                {results.map((result) => (
                  <div
                    key={result.ticker}
                    onClick={() => handleSelect(result.ticker)}
                    className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground"
                  >
                    <Check
                      className={cn(
                        'mr-2 h-4 w-4',
                        value === result.ticker
                          ? 'opacity-100'
                          : 'opacity-0'
                      )}
                    />
                    <div className="flex flex-col flex-1 min-w-0">
                      <div className="font-medium text-gray-900 truncate">
                        {highlightMatch(result.name)}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-sm text-blue-600 font-mono">
                          {highlightMatch(result.ticker)}
                        </span>
                        <span className="text-xs text-gray-500 px-1.5 py-0.5 bg-gray-100 rounded">
                          {result.type}
                        </span>
                        {result.exchange && (
                          <span className="text-xs text-gray-400">
                            {result.exchange}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
