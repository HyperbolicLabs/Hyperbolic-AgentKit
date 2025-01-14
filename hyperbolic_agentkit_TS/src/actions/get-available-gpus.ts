import { z } from 'zod';
import axios from 'axios';
import { HyperbolicAction } from './hyperbolic-action';
import { getApiKey } from '../utils/api';
import { APIError } from '../errors/base';
import { Environment } from '../types/environment';

const GET_AVAILABLE_GPUS_PROMPT = `
This tool will get all the available GPU machines on the Hyperbolic platform.

It does not take any following inputs

Important notes:
- Authorization key is required for this operation
- The GPU prices are in CENTS per hour
`;

/**
 * Input schema for getting available GPU machines
 */
export const GetAvailableGpusInputSchema = z.object({});
export type GetAvailableGpusInput = z.infer<typeof GetAvailableGpusInputSchema>;

/**
 * Get available GPUs from the Hyperbolic API
 * @param env The environment object containing API keys
 * @returns A promise that resolves to a string representation of the API response
 * @throws {APIError} If the API request fails
 * @throws {ConfigurationError} If the API key is not set
 */
async function getAvailableGpus(env: Partial<Environment>): Promise<string> {
  const apiKey = getApiKey(env);

  try {
    const response = await axios.post(
      'https://api.hyperbolic.xyz/v1/marketplace',
      { filters: {} },
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        }
      }
    );

    return JSON.stringify(response.data);
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new APIError(
        `Failed to get available GPUs: ${error.message}`,
        error.response?.status
      );
    }
    throw error;
  }
}

/**
 * Action class for getting available GPUs
 */
export class GetAvailableGpusAction extends HyperbolicAction<GetAvailableGpusInput> {
  constructor(env: Partial<Environment>) {
    super(
      'get_available_gpus',
      GET_AVAILABLE_GPUS_PROMPT,
      GetAvailableGpusInputSchema,
      async () => await getAvailableGpus(env)
    );
  }
}
