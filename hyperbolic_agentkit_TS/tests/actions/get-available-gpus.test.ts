import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { GetAvailableGpusAction } from '../../src/actions/get-available-gpus';
import { APIError } from '../../src/errors/base';
import { ConfigurationError } from '../../src/errors/configuration';

vi.mock('axios');

describe('GetAvailableGpusAction', () => {
  const mockApiKey = 'test-api-key';
  const mockEnv = { HYPERBOLIC_API_KEY: mockApiKey };
  let action: GetAvailableGpusAction;

  beforeEach(() => {
    vi.clearAllMocks();
    action = new GetAvailableGpusAction(mockEnv);
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      expect(action).toBeInstanceOf(GetAvailableGpusAction);
    });
  });

  describe('execute', () => {
    it('should get available GPUs successfully', async () => {
      const mockResponse = {
        data: {
          machines: [
            {
              id: 'gpu-1',
              gpu_type: 'RTX 4090',
              price_per_hour: 100,
            },
          ],
        },
      };

      vi.mocked(axios.post).mockResolvedValue(mockResponse);

      const result = await action.execute({});
      expect(result).toBe(JSON.stringify(mockResponse.data));

      expect(axios.post).toHaveBeenCalledWith(
        'https://api.hyperbolic.xyz/v1/marketplace',
        { filters: {} },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockApiKey}`,
          },
        }
      );
    });

    it('should handle API errors', async () => {
      const errorMessage = 'API request failed';
      vi.mocked(axios.post).mockRejectedValue({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 500 },
      });

      await expect(action.execute({})).rejects.toThrow(errorMessage);
    });

    it('should handle missing API key', async () => {
      action = new GetAvailableGpusAction({});
      await expect(action.execute({})).rejects.toThrow(
        'HYPERBOLIC_API_KEY environment variable is not set'
      );
    });
  });
});
