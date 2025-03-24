import { z } from 'zod';
import { Wallet, Amount } from '@coinbase/coinbase-sdk';
import { CdpAction } from './cdp-action';

const TRANSFER_PROMPT = `
This tool will transfer an asset from the wallet to another onchain address.

It takes the following inputs:
- amount: The amount to transfer
- assetId: The asset ID to transfer
- destination: Where to send the funds (can be an onchain address, ENS 'example.eth', or Basename 'example.base.eth')
- gasless: Whether to do a gasless transfer

Important notes:
- Gasless transfers are only available on base-sepolia and base-mainnet (base) networks for 'usdc' asset
- Always use gasless transfers when available
- Always use asset ID 'usdc' when transferring USDC
- Ensure sufficient balance of the input asset before transferring
- When sending native assets (e.g. 'eth' on base-mainnet), ensure there is sufficient balance for the transfer itself AND the gas cost of this transfer
`;

/**
 * Input schema for transfer action
 */
export const TransferInputSchema = z.object({
  amount: z.custom<Amount>().describe('The amount of the asset to transfer'),
  assetId: z.string().describe('The asset ID to transfer'),
  destination: z.string().describe('The destination to transfer the funds'),
  gasless: z.boolean().default(false).describe('Whether to do a gasless transfer')
});

export type TransferInput = z.infer<typeof TransferInputSchema>;

/**
 * Transfers a specified amount of an asset to a destination onchain
 */
async function transfer(
  wallet: Wallet,
  args: TransferInput
): Promise<string> {
  try {
    const transferResult = await wallet.createTransfer({
      amount: args.amount,
      assetId: args.assetId,
      destination: args.destination,
      gasless: args.gasless,
    });

    const result = await transferResult.wait();

    return `Transferred ${args.amount} of ${args.assetId} to ${args.destination}.
Transaction hash for the transfer: ${result.getTransactionHash()}
Transaction link for the transfer: ${result.getTransactionLink()}`;
  } catch (error) {
    return `Error transferring the asset: ${(error as Error).message}`;
  }
}

/**
 * Action class for transferring assets
 */
export class TransferAction extends CdpAction<typeof TransferInputSchema> {
  constructor(wallet: Wallet) {
    super(
      'transfer',
      TRANSFER_PROMPT,
      TransferInputSchema,
      wallet,
      transfer
    );
  }
}
