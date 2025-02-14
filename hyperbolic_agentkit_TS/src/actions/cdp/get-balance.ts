import { z } from 'zod';
import { Wallet } from '@coinbase/coinbase-sdk';
import Decimal from 'decimal.js';
import { CdpAction } from './cdp-action';

const GET_BALANCE_PROMPT = `
This tool will get the balance of all the addresses in the wallet for a given asset. 
It takes the asset ID as input. Always use 'eth' for the native asset ETH and 'usdc' for USDC.
`;

/**
 * Input schema for get balance action
 */
export const GetBalanceInputSchema = z.object({
  assetId: z.string().describe('The asset ID to get the balance for')
});

export type GetBalanceInput = z.infer<typeof GetBalanceInputSchema>;

/**
 * Gets balance for all addresses in the wallet for a given asset
 * @param wallet The wallet to get the balance for
 * @param args The input arguments for the action
 * @returns A promise that resolves to a message containing the balance information
 */
async function getBalance(
  wallet: Wallet,
  args: GetBalanceInput
): Promise<string> {
  const balances: Record<string, Decimal> = {};

  try {
    const addresses = await wallet.listAddresses();
    for (const address of addresses) {
      const balance = await address.getBalance(args.assetId);
      balances[address.getId()] = balance;
    }

    const balanceLines = Object.entries(balances).map(
      ([addr, balance]) => `${addr}: ${balance}`
    );
    const formattedBalances = balanceLines.join('\n');
    return `Balances for wallet ${wallet.getId()}:\n${formattedBalances}`;
  } catch (error) {
    return `Error getting balance for all addresses in the wallet: ${(error as Error).message}`;
  }
}

/**
 * Action class for getting wallet balance
 */
export class GetBalanceAction extends CdpAction<typeof GetBalanceInputSchema> {
  constructor(wallet: Wallet) {
    super(
      'get_balance',
      GET_BALANCE_PROMPT,
      GetBalanceInputSchema,
      wallet,
      getBalance
    );
  }
}
