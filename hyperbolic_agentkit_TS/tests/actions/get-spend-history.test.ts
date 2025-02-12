import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { GetSpendHistoryAction } from '../../src/actions/get-spend-history';
import { APIError } from '../../src/errors/base';
import { ConfigurationError } from '../../src/errors/configuration';

vi.mock('axios');

describe('GetSpendHistoryAction', () => {
  const mockApiKey = 'test-api-key';
  const mockEnv = { HYPERBOLIC_API_KEY: mockApiKey };
  let action: GetSpendHistoryAction;

  beforeEach(() => {
    vi.clearAllMocks();
    action = new GetSpendHistoryAction(mockEnv);
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      expect(action).toBeInstanceOf(GetSpendHistoryAction);
    });
  });

  describe('execute', () => {
    it('should get spend history successfully', async () => {
      const mockResponse = {
        data: {
          instances: [
            {
              instance_id: 'instance-1',
              start_time: '2025-01-14T12:00:00Z',
              end_time: '2025-01-14T13:00:00Z',
              cost: 5000,
              gpu_type: 'RTX 4090',
            },
            {
              instance_id: 'instance-2',
              start_time: '2025-01-13T12:00:00Z',
              end_time: '2025-01-13T14:00:00Z',
              cost: 10000,
              gpu_type: 'RTX 4090',
            },
          ],
        },
      };

      vi.mocked(axios.get).mockResolvedValue(mockResponse);

      const result = await action.execute({});
      const expected = JSON.stringify(mockResponse.data, null, 2);
      expect(result).toBe(expected);

      expect(axios.get).toHaveBeenCalledWith(
        'https://api.hyperbolic.xyz/v1/marketplace/instances/history',
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockApiKey}`,
          },
        }
      );
    });

    it('should handle empty instance history', async () => {
      const mockResponse = {
        data: {
          instances: [],
        },
      };

      vi.mocked(axios.get).mockResolvedValue(mockResponse);

      const result = await action.execute({});
      const expected = JSON.stringify(mockResponse.data, null, 2);
      expect(result).toBe(expected);
    });

    it('should handle missing instance data', async () => {
      const mockResponse = {
        data: {},
      };

      vi.mocked(axios.get).mockResolvedValue(mockResponse);

      const result = await action.execute({});
      const expected = JSON.stringify(mockResponse.data, null, 2);
      expect(result).toBe(expected);
    });

    it('should handle API errors', async () => {
      const errorMessage = 'API request failed';
      vi.mocked(axios.get).mockRejectedValue({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 500 },
      });

      await expect(action.execute({})).rejects.toThrow(errorMessage);
    });

    it('should handle unauthorized error', async () => {
      const errorMessage = 'Unauthorized';
      vi.mocked(axios.get).mockRejectedValue({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 401 },
      });

      await expect(action.execute({})).rejects.toThrow(errorMessage);
    });

    it('should handle missing API key', async () => {
      action = new GetSpendHistoryAction({});
      await expect(action.execute({})).rejects.toThrow(
        'HYPERBOLIC_API_KEY environment variable is not set'
      );
    });
  });
});
