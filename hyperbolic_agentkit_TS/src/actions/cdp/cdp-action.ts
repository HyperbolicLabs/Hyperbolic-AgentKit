import { z } from 'zod';
import { Wallet } from '@coinbase/coinbase-sdk';
import { HyperbolicAction } from '../hyperbolic-action';

/**
 * Base class for CDP actions that require wallet operations
 */
export abstract class CdpAction<T extends z.ZodType> extends HyperbolicAction<z.infer<T>> {
  protected wallet: Wallet;

  constructor(
    name: string,
    description: string,
    argsSchema: T,
    wallet: Wallet,
    func: (wallet: Wallet, args: z.infer<T>) => Promise<string>
  ) {
    super(
      name,
      description,
      argsSchema,
      async (args) => await func(wallet, args)
    );
    this.wallet = wallet;
  }
}
