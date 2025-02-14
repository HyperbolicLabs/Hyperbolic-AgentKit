import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { GetGpuStatusAction } from '../../src/actions/get-gpu-status';
import { APIError } from '../../src/errors/base';
import { ConfigurationError } from '../../src/errors/configuration';

vi.mock('axios');

describe('GetGpuStatusAction', () => {
  const mockApiKey = 'test-api-key';
  const mockEnv = { HYPERBOLIC_API_KEY: mockApiKey };
  let action: GetGpuStatusAction;

  beforeEach(() => {
    vi.clearAllMocks();
    action = new GetGpuStatusAction(mockEnv);
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      expect(action).toBeInstanceOf(GetGpuStatusAction);
    });
  });

  describe('execute', () => {
    it('should get GPU status successfully', async () => {
      const mockResponse = {
        data: {
          instances: [
            {
              id: 'instance-1',
              status: 'running',
              gpu_type: 'RTX 4090',
              ssh_command: 'ssh user@host',
            },
          ],
        },
      };

      vi.mocked(axios.get).mockResolvedValue(mockResponse);

      const result = await action.execute({});
      expect(result).toBe(JSON.stringify(mockResponse.data));

      expect(axios.get).toHaveBeenCalledWith(
        'https://api.hyperbolic.xyz/v1/marketplace/instances',
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
      vi.mocked(axios.get).mockRejectedValue({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 500 },
      });

      await expect(action.execute({})).rejects.toThrow(errorMessage);
    });

    it('should handle missing API key', async () => {
      action = new GetGpuStatusAction({});
      await expect(action.execute({})).rejects.toThrow(
        'HYPERBOLIC_API_KEY environment variable is not set'
      );
    });
  });
});
