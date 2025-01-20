import { z } from 'zod';
import axios from 'axios';
import { HyperbolicAction } from './hyperbolic-action';
import { ConfigurationError } from '../errors/configuration';
import { APIError } from '../errors/base';

const GET_SPEND_HISTORY_PROMPT = `
This tool retrieves and analyzes your GPU rental spending history from the Hyperbolic platform.
It provides information about:
- List of all instances rented
- Duration of each rental in seconds
- Cost per rental
- Total spending per GPU type
- Overall total spending
No input parameters required.
`;

const GetSpendHistorySchema = z.object({}).strict();

type GetSpendHistoryInput = z.infer<typeof GetSpendHistorySchema>;

/**
 * Action class for getting spend history
 */
export class GetSpendHistoryAction extends HyperbolicAction<GetSpendHistoryInput> {
  private readonly apiKey: string;

  constructor(env: Record<string, string>) {
    super(
      'get_spend_history',
      GET_SPEND_HISTORY_PROMPT,
      GetSpendHistorySchema,
      (args: GetSpendHistoryInput) => this.execute(args)
    );
    this.apiKey = env.HYPERBOLIC_API_KEY;
  }

  protected validateInput(input: GetSpendHistoryInput): GetSpendHistoryInput {
    return GetSpendHistorySchema.parse(input);
  }

  async execute(_input: GetSpendHistoryInput): Promise<string> {
    if (!this.apiKey) {
      throw new ConfigurationError('HYPERBOLIC_API_KEY environment variable is not set');
    }

    try {
      const response = await axios.get(
        'https://api.hyperbolic.xyz/v1/marketplace/instances/history',
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.apiKey}`,
          },
        }
      );

      // Return empty object if no data
      if (!response.data) {
        return JSON.stringify({}, null, 2);
      }

      // Return response data with pretty formatting
      return JSON.stringify(response.data, null, 2);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new APIError(`Failed to get spend history: ${error.message}`);
      }
      throw error;
    }
  }
}
