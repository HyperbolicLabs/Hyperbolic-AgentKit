import { z } from 'zod';
import axios from 'axios';
import { HyperbolicAction } from './hyperbolic-action';
import { getApiKey } from '../utils/api';
import { APIError } from '../errors/base';
import { Environment } from '../types/environment';

const GET_CURRENT_BALANCE_PROMPT = `
This tool retrieves your current Hyperbolic platform credit balance.
It shows:
- Available Hyperbolic platform credits in your account (in USD)
- Recent credit purchase history
Note: This is NOT for checking cryptocurrency wallet balances (ETH/USDC).
For crypto wallet balances, please use a different command.
No input parameters required.
`;

/**
 * Input schema for getting current balance
 */
export const GetCurrentBalanceInputSchema = z.object({});
export type GetCurrentBalanceInput = z.infer<typeof GetCurrentBalanceInputSchema>;

interface BalanceResponse {
  credits: number;
}

interface PurchaseHistory {
  amount: string;
  timestamp: string;
}

interface PurchaseHistoryResponse {
  purchase_history: PurchaseHistory[];
}

/**
 * Retrieve current balance and purchase history from the account
 * @param env The environment object containing API keys
 * @returns A promise that resolves to formatted current balance and purchase history information
 * @throws {APIError} If the API request fails
 */
async function getCurrentBalance(env: Partial<Environment>): Promise<string> {
  const apiKey = getApiKey(env);
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${apiKey}`
  };

  try {
    // Get current balance
    const balanceResponse = await axios.get<BalanceResponse>(
      'https://api.hyperbolic.xyz/billing/get_current_balance',
      { headers }
    );

    // Get purchase history
    const historyResponse = await axios.get<PurchaseHistoryResponse>(
      'https://api.hyperbolic.xyz/billing/purchase_history',
      { headers }
    );

    // Format the output
    const credits = balanceResponse.data.credits ?? 0;
    const balanceUsd = credits / 100; // Convert tokens to dollars

    const output: string[] = [`Your current Hyperbolic platform balance is $${balanceUsd.toFixed(2)}.`];

    const purchases = historyResponse.data.purchase_history ?? [];
    if (purchases.length > 0) {
      output.push('\nPurchase History:');
      for (const purchase of purchases) {
        const amount = parseFloat(purchase.amount) / 100;
        const timestamp = new Date(purchase.timestamp);
        const formattedDate = timestamp.toLocaleDateString('en-US', {
          month: 'long',
          day: 'numeric',
          year: 'numeric'
        });
        output.push(`- $${amount.toFixed(2)} on ${formattedDate}`);
      }
    } else {
      output.push('\nNo previous purchases found.');
    }

    return output.join('\n');
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new APIError(
        `Error retrieving balance information: ${error.message}`,
        error.response?.status
      );
    }
    throw error;
  }
}

/**
 * Action class for getting current balance
 */
export class GetCurrentBalanceAction extends HyperbolicAction<GetCurrentBalanceInput> {
  constructor(env: Partial<Environment>) {
    super(
      'get_current_balance',
      GET_CURRENT_BALANCE_PROMPT,
      GetCurrentBalanceInputSchema,
      async () => await getCurrentBalance(env)
    );
  }
}
