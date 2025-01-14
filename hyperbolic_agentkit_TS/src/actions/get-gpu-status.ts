import { z } from 'zod';
import axios from 'axios';
import { HyperbolicAction } from './hyperbolic-action';
import { getApiKey } from '../utils/api';
import { APIError } from '../errors/base';
import { Environment } from '../types/environment';

const GET_GPU_STATUS_PROMPT = `
This tool will get all the the status and ssh commands of you currently rented GPUs on the Hyperbolic platform.

It does not take any inputs

Important notes:
- Authorization key is required for this operation
- The GPU prices are in CENTS per hour
- If the status is "starting", it means the GPU is not ready yet. You can use the GetGPUStatus Action to check the status again after 5 seconds.
- You can access it through the SSHAccess Action and run commands on it through the RemoteShell Action.
`;

/**
 * Input schema for getting GPU status
 */
export const GetGpuStatusInputSchema = z.object({});
export type GetGpuStatusInput = z.infer<typeof GetGpuStatusInputSchema>;

/**
 * Get status of currently rented GPUs from the Hyperbolic API
 * @param env The environment object containing API keys
 * @returns A promise that resolves to a string representation of the API response
 * @throws {APIError} If the API request fails
 * @throws {ConfigurationError} If the API key is not set
 */
async function getGpuStatus(env: Partial<Environment>): Promise<string> {
  const apiKey = getApiKey(env);

  try {
    const response = await axios.get(
      'https://api.hyperbolic.xyz/v1/marketplace/instances',
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
        `Failed to get GPU status: ${error.message}`,
        error.response?.status
      );
    }
    throw error;
  }
}

/**
 * Action class for getting GPU status
 */
export class GetGpuStatusAction extends HyperbolicAction<GetGpuStatusInput> {
  constructor(env: Partial<Environment>) {
    super(
      'get_gpu_status',
      GET_GPU_STATUS_PROMPT,
      GetGpuStatusInputSchema,
      async () => await getGpuStatus(env)
    );
  }
}
