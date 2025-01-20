import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { SSHAccessAction, SSHAccessInput } from '../../src/actions/ssh-access';
import { SSHManager } from '../../src/utils/ssh-manager';

vi.mock('../../src/utils/ssh-manager');

describe('SSHAccessAction', () => {
  let sshAccessAction: SSHAccessAction;
  const mockEnv = { HYPERBOLIC_API_KEY: 'test-key' };
  const validInput: SSHAccessInput = {
    host: 'test-host',
    username: 'test-user',
    password: 'test-password',
    port: 22,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      sshAccessAction = new SSHAccessAction(mockEnv);
      expect(sshAccessAction).toBeInstanceOf(SSHAccessAction);
    });

    it('should validate input during execution', async () => {
      sshAccessAction = new SSHAccessAction(mockEnv);
      const inputWithKey = {
        ...validInput,
        password: undefined,
        privateKey: 'test-private-key',
      };
      const result = await sshAccessAction.execute(inputWithKey);
      expect(result).toContain('Successfully established SSH connection');
    });
  });

  describe('execute', () => {
    it('should execute SSH access successfully', async () => {
      const mockConnect = vi.fn().mockResolvedValue(undefined);
      const mockDisconnect = vi.fn();

      (SSHManager as Mock).mockImplementation(() => ({
        connect: mockConnect,
        disconnect: mockDisconnect,
        host: validInput.host,
      }));

      sshAccessAction = new SSHAccessAction(mockEnv);
      const result = await sshAccessAction.execute(validInput);
      expect(result).toBe(`Successfully established SSH connection to ${validInput.host}`);

      expect(mockConnect).toHaveBeenCalled();
      expect(mockDisconnect).toHaveBeenCalled();
    });

    it('should handle SSH access errors', async () => {
      const errorMessage = 'Connection failed';
      const mockConnect = vi.fn().mockRejectedValue(new Error(errorMessage));
      const mockDisconnect = vi.fn();

      (SSHManager as Mock).mockImplementation(() => ({
        connect: mockConnect,
        disconnect: mockDisconnect,
        host: validInput.host,
      }));

      sshAccessAction = new SSHAccessAction(mockEnv);
      const result = await sshAccessAction.execute(validInput);
      expect(result).toBe(`Failed to establish SSH connection: ${errorMessage}`);

      expect(mockConnect).toHaveBeenCalled();
      expect(mockDisconnect).toHaveBeenCalled();
    });

    it('should validate input before execution', async () => {
      sshAccessAction = new SSHAccessAction(mockEnv);
      const invalidInput = {
        ...validInput,
        password: undefined,
        privateKey: undefined,
      };
      
      await expect(sshAccessAction.execute(invalidInput)).rejects.toThrow(
        'Either password or privateKey/privateKeyPath must be provided'
      );
    });
  });
});
