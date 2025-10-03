import { useState, useEffect, useRef, useCallback } from 'react';
import { getRealtimePrices } from '@/lib/api';
import type { RealtimePrice } from '@/lib/types';

const POLLING_INTERVAL = 30000; // 30 seconds
const DEBOUNCE_DELAY = 500; // 500ms debounce for rapid updates

interface UseRealtimePricesReturn {
  realtimePrices: Map<string, RealtimePrice>;
  isLoading: boolean;
  error: Error | null;
  lastUpdate: Date | null;
}

export function useRealtimePrices(): UseRealtimePricesReturn {
  const [realtimePrices, setRealtimePrices] = useState<Map<string, RealtimePrice>>(new Map());
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isVisibleRef = useRef<boolean>(true);

  const fetchPrices = useCallback(async () => {
    try {
      const prices = await getRealtimePrices();

      // Debounce the state update to prevent UI flickering
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(() => {
        const priceMap = new Map<string, RealtimePrice>();
        prices.forEach((price) => {
          priceMap.set(price.ticker, price);
        });

        setRealtimePrices(priceMap);
        setLastUpdate(new Date());
        setError(null);
        setIsLoading(false);
      }, DEBOUNCE_DELAY);
    } catch (err) {
      console.error('Failed to fetch realtime prices:', err);
      setError(err instanceof Error ? err : new Error('Failed to fetch realtime prices'));
      setIsLoading(false);
    }
  }, []);

  const startPolling = useCallback(() => {
    // Clear existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    // Fetch immediately
    fetchPrices();

    // Set up polling interval
    intervalRef.current = setInterval(() => {
      if (isVisibleRef.current) {
        fetchPrices();
      }
    }, POLLING_INTERVAL);
  }, [fetchPrices]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
  }, []);

  // Handle page visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      isVisibleRef.current = !document.hidden;

      if (document.hidden) {
        // Page is hidden, stop polling
        stopPolling();
      } else {
        // Page is visible again, restart polling
        startPolling();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [startPolling, stopPolling]);

  // Handle window focus events for additional responsiveness
  useEffect(() => {
    const handleFocus = () => {
      if (!document.hidden) {
        // Refresh immediately when window gains focus
        fetchPrices();
      }
    };

    window.addEventListener('focus', handleFocus);

    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [fetchPrices]);

  // Start polling on mount
  useEffect(() => {
    startPolling();

    return () => {
      stopPolling();
    };
  }, [startPolling, stopPolling]);

  return {
    realtimePrices,
    isLoading,
    error,
    lastUpdate,
  };
}
