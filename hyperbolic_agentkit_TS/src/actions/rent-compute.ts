import { z } from 'zod';
import axios from 'axios';
import { HyperbolicAction } from './hyperbolic-action';
import { getApiKey } from '../utils/api';
import { APIError, ValidationError } from '../errors/base';
import { Environment } from '../types/environment';

const RENT_COMPUTE_PROMPT = `
This tool will allow you to rent a GPU machine on Hyperbolic platform. 

It takes the following inputs:
- cluster_name: Which cluster the node is on
- node_name: Which node the user wants to rent
- gpu_count: How many GPUs the user wants to rent

Important notes:
- All inputs must be recognized in order to process the rental
- If the inputs are not recognized, automatically use the GetAvailableGpus Action to get the available GPUs
- After renting, you will be able to find it through the GetGPUStatus Action, access it through the SSHAccess Action and run commands on it through the RemoteShell Action.
`;

/**
 * Input schema for compute rental action
 */
export const RentComputeInputSchema = z.object({
  cluster_name: z.string().min(1, 'Cluster name is required'),
  node_name: z.string().min(1, 'Node name is required'),
  gpu_count: z.string().min(1, 'GPU count is required')
});

export type RentComputeInput = z.infer<typeof RentComputeInputSchema>;

/**
 * Creates a marketplace instance using the Hyperbolic API
 * @param env The environment object containing API keys
 * @param args The rental arguments
 * @returns A promise that resolves to a formatted string representation of the API response
 * @throws {ValidationError} If required parameters are invalid
 * @throws {APIError} If the API request fails
 */
async function rentCompute(
  env: Partial<Environment>,
  args: RentComputeInput
): Promise<string> {
  const { cluster_name, node_name, gpu_count } = args;

  // Input validation
  if (!cluster_name || !node_name || !gpu_count) {
    throw new ValidationError('cluster_name, node_name, and gpu_count are required');
  }

  const apiKey = getApiKey(env);

  try {
    const response = await axios.post(
      'https://api.hyperbolic.xyz/v1/marketplace/instances/create',
      {
        cluster_name,
        node_name,
        gpu_count
      },
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
      let errorMessage = `Error renting compute from Hyperbolic marketplace: ${error.message}`;
      
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
 * Action class for renting compute resources
 */
export class RentComputeAction extends HyperbolicAction<RentComputeInput> {
  constructor(env: Partial<Environment>) {
    super(
      'rent_compute',
      RENT_COMPUTE_PROMPT,
      RentComputeInputSchema,
      async (args) => await rentCompute(env, args)
    );
  }
}
