import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { GetCurrentBalanceAction } from '../../src/actions/get-current-balance';
import { APIError } from '../../src/errors/base';
import { ConfigurationError } from '../../src/errors/configuration';

vi.mock('axios');

describe('GetCurrentBalanceAction', () => {
  const mockApiKey = 'test-api-key';
  const mockEnv = { HYPERBOLIC_API_KEY: mockApiKey };
  let action: GetCurrentBalanceAction;

  beforeEach(() => {
    vi.clearAllMocks();
    action = new GetCurrentBalanceAction(mockEnv);
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      expect(action).toBeInstanceOf(GetCurrentBalanceAction);
    });
  });

  describe('execute', () => {
    it('should get current balance and purchase history successfully', async () => {
      const mockBalanceResponse = {
        data: {
          credits: 10000, // $100.00
        },
      };

      const mockPurchaseHistoryResponse = {
        data: {
          purchase_history: [
            {
              amount: '5000', // $50.00
              timestamp: '2025-01-14T12:00:00Z',
            },
            {
              amount: '5000', // $50.00
              timestamp: '2025-01-13T12:00:00Z',
            },
          ],
        },
      };

      vi.mocked(axios.get)
        .mockResolvedValueOnce(mockBalanceResponse)
        .mockResolvedValueOnce(mockPurchaseHistoryResponse);

      const result = await action.execute({});
      expect(result).toBe(
        'Your current Hyperbolic platform balance is $100.00.\n\n' +
        'Purchase History:\n' +
        '- $50.00 on January 14, 2025\n' +
        '- $50.00 on January 13, 2025'
      );

      expect(axios.get).toHaveBeenNthCalledWith(1,
        'https://api.hyperbolic.xyz/billing/get_current_balance',
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockApiKey}`,
          },
        }
      );

      expect(axios.get).toHaveBeenNthCalledWith(2,
        'https://api.hyperbolic.xyz/billing/purchase_history',
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockApiKey}`,
          },
        }
      );
    });

    it('should handle empty purchase history', async () => {
      const mockBalanceResponse = {
        data: {
          credits: 10000, // $100.00
        },
      };

      const mockPurchaseHistoryResponse = {
        data: {
          purchase_history: [],
        },
      };

      vi.mocked(axios.get)
        .mockResolvedValueOnce(mockBalanceResponse)
        .mockResolvedValueOnce(mockPurchaseHistoryResponse);

      const result = await action.execute({});
      expect(result).toBe(
        'Your current Hyperbolic platform balance is $100.00.\n\n' +
        'No previous purchases found.'
      );
    });

    it('should handle missing balance data', async () => {
      const mockBalanceResponse = {
        data: {},
      };

      const mockPurchaseHistoryResponse = {
        data: {
          purchase_history: [],
        },
      };

      vi.mocked(axios.get)
        .mockResolvedValueOnce(mockBalanceResponse)
        .mockResolvedValueOnce(mockPurchaseHistoryResponse);

      const result = await action.execute({});
      expect(result).toBe(
        'Your current Hyperbolic platform balance is $0.00.\n\n' +
        'No previous purchases found.'
      );
    });

    it('should handle API errors - balance request', async () => {
      const errorMessage = 'Failed to fetch balance';
      vi.mocked(axios.get).mockRejectedValueOnce({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 500 },
      });

      await expect(action.execute({})).rejects.toThrow(errorMessage);
    });

    it('should handle API errors - purchase history request', async () => {
      const mockBalanceResponse = {
        data: {
          credits: 10000,
        },
      };

      const errorMessage = 'Failed to fetch purchase history';
      vi.mocked(axios.get)
        .mockResolvedValueOnce(mockBalanceResponse)
        .mockRejectedValueOnce({
          isAxiosError: true,
          message: errorMessage,
          response: { status: 500 },
        });

      await expect(action.execute({})).rejects.toThrow(errorMessage);
    });

    it('should handle missing API key', async () => {
      action = new GetCurrentBalanceAction({});
      await expect(action.execute({})).rejects.toThrow(
        'HYPERBOLIC_API_KEY environment variable is not set'
      );
    });
  });
});
