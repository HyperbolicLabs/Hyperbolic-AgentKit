import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { Wallet, Coinbase } from '@coinbase/coinbase-sdk';
import { RegisterBasenameAction, RegisterBasenameInput } from '../../../src/actions/cdp/register-basename';
import { Decimal } from 'decimal.js';

vi.mock('@coinbase/coinbase-sdk');
vi.mock('viem', () => ({
  encodeFunctionData: vi.fn().mockReturnValue('0x123'),
  namehash: vi.fn().mockReturnValue('0x456')
}));

describe('RegisterBasenameAction', () => {
  let registerBasenameAction: RegisterBasenameAction;
  let mockWallet: Wallet;
  
  const validInput: RegisterBasenameInput = {
    basename: 'example.base.eth',
    amount: '0.002'
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock transaction
    const mockTxResult = {
      wait: vi.fn().mockResolvedValue({
        hash: '0xabc',
        status: 'success'
      })
    };

    // Mock address
    const mockAddress = {
      getId: vi.fn().mockReturnValue('0x789')
    };

    mockWallet = {
      getDefaultAddress: vi.fn().mockResolvedValue(mockAddress),
      getNetworkId: vi.fn().mockReturnValue(Coinbase.networks.BaseMainnet),
      invokeContract: vi.fn().mockResolvedValue(mockTxResult)
    } as unknown as Wallet;

    registerBasenameAction = new RegisterBasenameAction(mockWallet);
  });

  describe('execute', () => {
    it('should register basename successfully on mainnet', async () => {
      const result = await registerBasenameAction.execute(validInput);
      
      expect(mockWallet.invokeContract).toHaveBeenCalledWith({
        contractAddress: expect.any(String),
        method: 'register',
        args: expect.any(Object),
        abi: expect.any(Array),
        amount: new Decimal('0.002'),
        assetId: 'eth'
      });
      expect(result).toContain('Successfully registered');
      expect(result).toContain('example.base.eth');
    });

    it('should register basename successfully on testnet', async () => {
      const testnetInput: RegisterBasenameInput = {
        basename: 'example.basetest.eth',
        amount: '0.002'
      };

      (mockWallet.getNetworkId as Mock).mockReturnValue(Coinbase.networks.BaseSepolia);

      const result = await registerBasenameAction.execute(testnetInput);
      
      expect(mockWallet.invokeContract).toHaveBeenCalledWith({
        contractAddress: expect.any(String),
        method: 'register',
        args: expect.any(Object),
        abi: expect.any(Array),
        amount: new Decimal('0.002'),
        assetId: 'eth'
      });
      expect(result).toContain('Successfully registered');
      expect(result).toContain('example.basetest.eth');
    });

    it('should handle registration errors', async () => {
      const error = new Error('Registration failed');
      (mockWallet.invokeContract as Mock).mockRejectedValue(error);

      const result = await registerBasenameAction.execute(validInput);
      expect(result).toContain('Error registering basename');
      expect(result).toContain(error.message);
    });

    it('should validate basename format for mainnet', async () => {
      const invalidInput: RegisterBasenameInput = {
        basename: 'example.eth',
        amount: '0.002'
      };

      const result = await registerBasenameAction.execute(invalidInput);
      expect(result).toContain('example.eth.base.eth');
    });

    it('should validate basename format for testnet', async () => {
      const invalidInput: RegisterBasenameInput = {
        basename: 'example.base.eth',
        amount: '0.002'
      };

      (mockWallet.getNetworkId as Mock).mockReturnValue(Coinbase.networks.BaseSepolia);

      const result = await registerBasenameAction.execute(invalidInput);
      expect(result).toContain('example.base.eth.basetest.eth');
    });
  });
});
