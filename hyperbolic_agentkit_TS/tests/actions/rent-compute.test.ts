import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { RentComputeAction } from '../../src/actions/rent-compute';
import { APIError } from '../../src/errors/base';
import { ConfigurationError } from '../../src/errors/configuration';
import { ValidationError } from '../../src/errors/validation';

vi.mock('axios');

describe('RentComputeAction', () => {
  const mockApiKey = 'test-api-key';
  const mockEnv = { HYPERBOLIC_API_KEY: mockApiKey };
  let action: RentComputeAction;

  const validInput = {
    cluster_name: 'test-cluster',
    node_name: 'test-node',
    gpu_count: '1',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    action = new RentComputeAction(mockEnv);
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      expect(action).toBeInstanceOf(RentComputeAction);
    });
  });

  describe('execute', () => {
    it('should rent compute successfully', async () => {
      const mockResponse = {
        data: {
          instance_id: 'test-instance-id',
          status: 'provisioning',
          ssh_command: 'ssh user@host',
        },
      };

      vi.mocked(axios.post).mockResolvedValue(mockResponse);

      const result = await action.execute(validInput);
      const expected = JSON.stringify(mockResponse.data, null, 2);
      expect(result).toBe(expected);

      expect(axios.post).toHaveBeenCalledWith(
        'https://api.hyperbolic.xyz/v1/marketplace/instances/create',
        {
          cluster_name: validInput.cluster_name,
          node_name: validInput.node_name,
          gpu_count: validInput.gpu_count,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockApiKey}`,
          },
        }
      );
    });

    it('should handle validation errors - missing cluster_name', async () => {
      const input = { ...validInput, cluster_name: '' };
      await expect(action.execute(input)).rejects.toThrow('Invalid arguments');
    });

    it('should handle validation errors - missing node_name', async () => {
      const input = { ...validInput, node_name: '' };
      await expect(action.execute(input)).rejects.toThrow('Invalid arguments');
    });

    it('should handle validation errors - missing gpu_count', async () => {
      const input = { ...validInput, gpu_count: '' };
      await expect(action.execute(input)).rejects.toThrow('Invalid arguments');
    });

    it('should handle API errors', async () => {
      const errorMessage = 'API request failed';
      vi.mocked(axios.post).mockRejectedValue({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 500 },
      });

      await expect(action.execute(validInput)).rejects.toThrow(errorMessage);
    });

    it('should handle missing API key', async () => {
      action = new RentComputeAction({});
      await expect(action.execute(validInput)).rejects.toThrow(
        'HYPERBOLIC_API_KEY environment variable is not set'
      );
    });
  });
});
