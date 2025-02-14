import { z } from 'zod';
import axios from 'axios';
import { HyperbolicAction } from './hyperbolic-action';
import { getApiKey } from '../utils/api';
import { APIError, ValidationError } from '../errors/base';
import { Environment } from '../types/environment';

const TERMINATE_COMPUTE_PROMPT = `
This tool allows you to terminate a GPU instance on the Hyperbolic platform.
It takes the following input:
- instance_id: The ID of the instance to terminate (e.g., "respectful-rose-pelican")
Important notes:
- The instance ID must be valid and active
- After termination, the instance will no longer be accessible
- You can get instance IDs using the GetGPUStatus Action
`;

/**
 * Input schema for compute termination action
 */
export const TerminateComputeInputSchema = z.object({
  instance_id: z.string().min(1, 'Instance ID is required')
});

export type TerminateComputeInput = z.infer<typeof TerminateComputeInputSchema>;

/**
 * Terminates a marketplace instance using the Hyperbolic API
 * @param env The environment object containing API keys
 * @param args The termination arguments
 * @returns A promise that resolves to a formatted string representation of the API response
 * @throws {ValidationError} If instance_id is invalid
 * @throws {APIError} If the API request fails
 */
async function terminateCompute(
  env: Partial<Environment>,
  args: TerminateComputeInput
): Promise<string> {
  const { instance_id } = args;

  // Input validation
  if (!instance_id) {
    throw new ValidationError('instance_id is required');
  }

  const apiKey = getApiKey(env);

  try {
    const response = await axios.post(
      'https://api.hyperbolic.xyz/v1/marketplace/instances/terminate',
      { id: instance_id },
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        }
      }
    );

    return JSON.stringify(response.data, null, 2);
  } catch (error) {
    if (axios.isAxiosError(error)) {
      let errorMessage = `Error terminating compute instance: ${error.message}`;
      
      if (error.response) {
        const responseData = error.response.data;
        errorMessage += `\nResponse: ${JSON.stringify(responseData, null, 2)}`;
      }

      throw new APIError(errorMessage, error.response?.status);
    }
    throw error;
  }
}

/**
 * Action class for terminating compute resources
 */
export class TerminateComputeAction extends HyperbolicAction<TerminateComputeInput> {
  constructor(env: Partial<Environment>) {
    super(
      'terminate_compute',
      TERMINATE_COMPUTE_PROMPT,
      TerminateComputeInputSchema,
      async (args) => await terminateCompute(env, args)
    );
  }
}
