/**
 * Tests for API transformation functions in lib/api.ts
 *
 * These tests verify that frontend data is properly transformed
 * to match backend expectations before sending requests.
 */

describe('API Transformation Functions', () => {
  describe('transformTransactionForBackend', () => {
    let transformTransactionForBackend: any;

    beforeAll(() => {
      // Import the function from api.ts
      // Note: This requires the function to be exported
      const apiModule = require('../api');
      transformTransactionForBackend = apiModule.transformTransactionForBackend;
    });

    it('should transform transaction_type to type and lowercase it', () => {
      const input = {
        transaction_type: 'BUY',
        date: '2025-10-20',
        ticker: 'AAPL',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 0,
      };

      const output = transformTransactionForBackend(input);

      expect(output.type).toBe('buy');
      expect(output.transaction_type).toBeUndefined();
    });

    it('should transform date to operation_date', () => {
      const input = {
        transaction_type: 'SELL',
        date: '2025-10-20',
        ticker: 'MSFT',
        quantity: 5,
        amount: 350.00,
        currency: 'EUR',
        fees: 10,
      };

      const output = transformTransactionForBackend(input);

      expect(output.operation_date).toBe('2025-10-20');
      expect(output.date).toBeUndefined();
    });

    it('should remove isin field from transformation', () => {
      const input = {
        transaction_type: 'BUY',
        date: '2025-10-20',
        ticker: 'AAPL',
        isin: 'US0378331005',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 0,
      };

      const output = transformTransactionForBackend(input);

      expect(output.isin).toBeUndefined();
    });

    it('should remove broker field from transformation', () => {
      const input = {
        transaction_type: 'BUY',
        date: '2025-10-20',
        ticker: 'AAPL',
        broker: 'Directa',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 0,
      };

      const output = transformTransactionForBackend(input);

      expect(output.broker).toBeUndefined();
    });

    it('should remove description field from transformation', () => {
      const input = {
        transaction_type: 'BUY',
        date: '2025-10-20',
        ticker: 'AAPL',
        description: 'Apple Inc.',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 0,
      };

      const output = transformTransactionForBackend(input);

      expect(output.description).toBeUndefined();
    });

    it('should preserve all other fields in the transformation', () => {
      const input = {
        transaction_type: 'BUY',
        date: '2025-10-20',
        ticker: 'GOOGL',
        quantity: 20,
        amount: 140.00,
        currency: 'USD',
        fees: 5.50,
        order_reference: 'ORDER-123',
      };

      const output = transformTransactionForBackend(input);

      expect(output.ticker).toBe('GOOGL');
      expect(output.quantity).toBe(20);
      expect(output.amount).toBe(140.00);
      expect(output.currency).toBe('USD');
      expect(output.fees).toBe(5.50);
      expect(output.order_reference).toBe('ORDER-123');
    });

    it('should handle lowercase transaction_type input', () => {
      const input = {
        transaction_type: 'buy',
        date: '2025-10-20',
        ticker: 'AAPL',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 0,
      };

      const output = transformTransactionForBackend(input);

      expect(output.type).toBe('buy');
    });

    it('should default to "buy" if transaction_type is missing', () => {
      const input = {
        date: '2025-10-20',
        ticker: 'AAPL',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 0,
      };

      const output = transformTransactionForBackend(input);

      expect(output.type).toBe('buy');
    });

    it('should handle mixed case transaction types', () => {
      const testCases = [
        { input: 'BUY', expected: 'buy' },
        { input: 'SELL', expected: 'sell' },
        { input: 'Buy', expected: 'buy' },
        { input: 'Sell', expected: 'sell' },
        { input: 'buY', expected: 'buy' },
      ];

      testCases.forEach(({ input, expected }) => {
        const transactionData = {
          transaction_type: input,
          date: '2025-10-20',
          ticker: 'AAPL',
          quantity: 10,
          amount: 150.00,
          currency: 'EUR',
          fees: 0,
        };

        const output = transformTransactionForBackend(transactionData);
        expect(output.type).toBe(expected);
      });
    });

    it('should handle complete transaction with all fields', () => {
      const input = {
        transaction_type: 'BUY',
        date: '2025-10-20',
        ticker: 'AAPL',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 2.50,
        isin: 'US0378331005',
        broker: 'Directa',
        description: 'Apple Inc.',
        order_reference: 'ORDER-12345',
      };

      const output = transformTransactionForBackend(input);

      expect(output).toEqual({
        type: 'buy',
        operation_date: '2025-10-20',
        ticker: 'AAPL',
        quantity: 10,
        amount: 150.00,
        currency: 'EUR',
        fees: 2.50,
        order_reference: 'ORDER-12345',
      });

      // Verify removed fields
      expect(output.isin).toBeUndefined();
      expect(output.broker).toBeUndefined();
      expect(output.description).toBeUndefined();
      expect(output.date).toBeUndefined();
      expect(output.transaction_type).toBeUndefined();
    });
  });

  describe('normalizeTransactionType', () => {
    let normalizeTransactionType: any;

    beforeAll(() => {
      // Import the function from api.ts
      // Note: This requires the function to be exported
      const apiModule = require('../api');
      normalizeTransactionType = apiModule.normalizeTransactionType;
    });

    it('should lowercase transaction_type field', () => {
      const input = { transaction_type: 'BUY' };
      const output = normalizeTransactionType(input);

      expect(output.transaction_type).toBe('buy');
    });

    it('should preserve other fields unchanged', () => {
      const input = {
        transaction_type: 'SELL',
        ticker: 'MSFT',
        quantity: 5,
      };

      const output = normalizeTransactionType(input);

      expect(output.ticker).toBe('MSFT');
      expect(output.quantity).toBe(5);
    });

    it('should handle missing transaction_type', () => {
      const input = { ticker: 'AAPL', quantity: 10 };
      const output = normalizeTransactionType(input);

      expect(output).toEqual(input);
    });

    it('should not modify input object', () => {
      const input = { transaction_type: 'BUY', ticker: 'AAPL' };
      const inputCopy = { ...input };

      normalizeTransactionType(input);

      expect(input).toEqual(inputCopy);
    });
  });
});
