'use client';

import { useState, useEffect } from 'react';
import { Check, ChevronsUpDown, Loader2 } from 'lucide-react';
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
  placeholder = 'Select benchmark ticker...',
  disabled = false,
}: TickerAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Debounce search
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 1) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const data = await searchTickers(searchQuery);
        setResults(data);
      } catch (error) {
        console.error('Error searching tickers:', error);
        setResults([]);
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
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search ticker or index name..."
            value={searchQuery}
            onValueChange={setSearchQuery}
          />
          <CommandList>
            {isLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
              </div>
            ) : results.length === 0 ? (
              <CommandEmpty>
                {searchQuery
                  ? 'No tickers found. Try a different search term.'
                  : 'Start typing to search for tickers...'}
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
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{result.ticker}</span>
                        <span className="text-xs text-gray-500 px-1.5 py-0.5 bg-gray-100 rounded">
                          {result.type}
                        </span>
                      </div>
                      <span className="text-sm text-gray-600">
                        {result.name}
                      </span>
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
