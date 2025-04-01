import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { Wallet, Address } from '@coinbase/coinbase-sdk';
import Decimal from 'decimal.js';
import { GetBalanceAction, GetBalanceInput } from '../../../src/actions/cdp/get-balance';

vi.mock('@coinbase/coinbase-sdk');

describe('GetBalanceAction', () => {
  let getBalanceAction: GetBalanceAction;
  let mockWallet: Wallet;
  const validInput: GetBalanceInput = {
    assetId: 'eth'
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock wallet and addresses
    const mockAddress1 = {
      getId: vi.fn().mockReturnValue('addr1'),
      getBalance: vi.fn().mockResolvedValue(new Decimal('1.5'))
    } as unknown as Address;

    const mockAddress2 = {
      getId: vi.fn().mockReturnValue('addr2'),
      getBalance: vi.fn().mockResolvedValue(new Decimal('2.5'))
    } as unknown as Address;

    mockWallet = {
      getId: vi.fn().mockReturnValue('wallet1'),
      listAddresses: vi.fn().mockResolvedValue([mockAddress1, mockAddress2])
    } as unknown as Wallet;

    getBalanceAction = new GetBalanceAction(mockWallet);
  });

  describe('execute', () => {
    it('should get balance for all addresses successfully', async () => {
      const result = await getBalanceAction.execute(validInput);
      expect(result).toContain('Balances for wallet wallet1');
      expect(result).toContain('addr1: 1.5');
      expect(result).toContain('addr2: 2.5');
      expect(mockWallet.listAddresses).toHaveBeenCalled();
    });

    it('should handle errors when getting balance', async () => {
      const error = new Error('Failed to get balance');
      (mockWallet.listAddresses as Mock).mockRejectedValue(error);

      const result = await getBalanceAction.execute(validInput);
      expect(result).toContain('Error getting balance');
      expect(result).toContain(error.message);
    });

    it('should validate input before execution', async () => {
      const invalidInput = {} as GetBalanceInput;
      await expect(getBalanceAction.execute(invalidInput)).rejects.toThrow();
    });
  });
});
