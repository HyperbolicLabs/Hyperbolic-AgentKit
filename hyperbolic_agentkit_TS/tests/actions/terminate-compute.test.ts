import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { TerminateComputeAction } from '../../src/actions/terminate-compute';
import { APIError } from '../../src/errors/base';
import { ConfigurationError } from '../../src/errors/configuration';
import { ValidationError } from '../../src/errors/validation';

vi.mock('axios');

describe('TerminateComputeAction', () => {
  const mockApiKey = 'test-api-key';
  const mockEnv = { HYPERBOLIC_API_KEY: mockApiKey };
  let action: TerminateComputeAction;

  const validInput = {
    instance_id: 'test-instance-id',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    action = new TerminateComputeAction(mockEnv);
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      expect(action).toBeInstanceOf(TerminateComputeAction);
    });
  });

  describe('execute', () => {
    it('should terminate compute successfully', async () => {
      const mockResponse = {
        data: {
          instance_id: validInput.instance_id,
          status: 'terminated',
        },
      };

      vi.mocked(axios.post).mockResolvedValue(mockResponse);

      const result = await action.execute(validInput);
      const expected = JSON.stringify(mockResponse.data, null, 2);
      expect(result).toBe(expected);

      expect(axios.post).toHaveBeenCalledWith(
        'https://api.hyperbolic.xyz/v1/marketplace/instances/terminate',
        { id: validInput.instance_id },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockApiKey}`,
          },
        }
      );
    });

    it('should handle validation errors - missing instance_id', async () => {
      const input = { instance_id: '' };
      await expect(action.execute(input)).rejects.toThrow('Invalid arguments');
    });

    it('should handle API errors - instance not found', async () => {
      const errorMessage = 'Instance not found';
      vi.mocked(axios.post).mockRejectedValue({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 404 },
      });

      await expect(action.execute(validInput)).rejects.toThrow(errorMessage);
    });

    it('should handle API errors - unauthorized', async () => {
      const errorMessage = 'Unauthorized';
      vi.mocked(axios.post).mockRejectedValue({
        isAxiosError: true,
        message: errorMessage,
        response: { status: 401 },
      });

      await expect(action.execute(validInput)).rejects.toThrow(errorMessage);
    });

    it('should handle missing API key', async () => {
      action = new TerminateComputeAction({});
      await expect(action.execute(validInput)).rejects.toThrow(
        'HYPERBOLIC_API_KEY environment variable is not set'
      );
    });
  });
});
