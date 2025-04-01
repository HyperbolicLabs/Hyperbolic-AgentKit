import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { Wallet, Amount } from '@coinbase/coinbase-sdk';
import { TransferAction, TransferInput } from '../../../src/actions/cdp/transfer';

vi.mock('@coinbase/coinbase-sdk');

describe('TransferAction', () => {
  let transferAction: TransferAction;
  let mockWallet: Wallet;
  const mockAmount = 100 as Amount;
  
  const validInput: TransferInput = {
    amount: mockAmount,
    assetId: 'usdc',
    destination: 'example.base.eth',
    gasless: true
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock transfer result
    const mockTransferResult = {
      wait: vi.fn().mockResolvedValue({
        getTransactionHash: vi.fn().mockReturnValue('0x123'),
        getTransactionLink: vi.fn().mockReturnValue('https://example.com/tx/0x123')
      })
    };

    mockWallet = {
      createTransfer: vi.fn().mockResolvedValue(mockTransferResult)
    } as unknown as Wallet;

    transferAction = new TransferAction(mockWallet);
  });

  describe('execute', () => {
    it('should execute transfer successfully', async () => {
      const result = await transferAction.execute(validInput);
      
      expect(mockWallet.createTransfer).toHaveBeenCalledWith({
        amount: mockAmount,
        assetId: 'usdc',
        destination: 'example.base.eth',
        gasless: true
      });
      
      expect(result).toContain('Transferred');
      expect(result).toContain('usdc');
      expect(result).toContain('example.base.eth');
      expect(result).toContain('0x123');
    });

    it('should handle transfer errors', async () => {
      const error = new Error('Transfer failed');
      (mockWallet.createTransfer as Mock).mockRejectedValue(error);

      const result = await transferAction.execute(validInput);
      expect(result).toContain('Error transferring the asset');
      expect(result).toContain('Transfer failed');
    });

    it('should handle non-gasless transfers', async () => {
      const nonGaslessInput = {
        ...validInput,
        gasless: false
      };

      await transferAction.execute(nonGaslessInput);
      
      expect(mockWallet.createTransfer).toHaveBeenCalledWith({
        amount: mockAmount,
        assetId: 'usdc',
        destination: 'example.base.eth',
        gasless: false
      });
    });

    it('should validate input before execution', async () => {
      const invalidInput = {
        ...validInput,
        amount: undefined
      } as unknown as TransferInput;

      // Mock createTransfer to throw error for invalid input
      (mockWallet.createTransfer as Mock).mockRejectedValue(new Error('Invalid amount'));

      const result = await transferAction.execute(invalidInput);
      expect(result).toContain('Error transferring the asset');
      expect(result).toContain('Invalid amount');
    });
  });
});
