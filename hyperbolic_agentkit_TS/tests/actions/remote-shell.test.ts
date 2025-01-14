import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { RemoteShellAction, RemoteShellInput } from '../../src/actions/remote-shell';
import { SSHManager } from '../../src/utils/ssh-manager';

vi.mock('../../src/utils/ssh-manager');

describe('RemoteShellAction', () => {
  let remoteShellAction: RemoteShellAction;
  const mockEnv = { HYPERBOLIC_API_KEY: 'test-key' };
  const validInput: RemoteShellInput = {
    host: 'test-host',
    username: 'test-user',
    password: 'test-password',
    port: 22,
    command: 'ls -la',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('constructor', () => {
    it('should create instance with valid input', () => {
      remoteShellAction = new RemoteShellAction(mockEnv);
      expect(remoteShellAction).toBeInstanceOf(RemoteShellAction);
    });
  });

  describe('execute', () => {
    it('should execute command successfully', async () => {
      const mockConnect = vi.fn();
      const mockExecuteCommand = vi.fn().mockResolvedValue({
        output: 'command output',
        exitCode: 0,
      });
      const mockDisconnect = vi.fn();

      (SSHManager as Mock).mockImplementation(() => ({
        connect: mockConnect,
        executeCommand: mockExecuteCommand,
        disconnect: mockDisconnect,
      }));

      remoteShellAction = new RemoteShellAction(mockEnv);
      const result = await remoteShellAction.execute(validInput);
      const parsedResult = JSON.parse(result);

      expect(mockConnect).toHaveBeenCalled();
      expect(mockExecuteCommand).toHaveBeenCalledWith(validInput.command);
      expect(mockDisconnect).toHaveBeenCalled();
      expect(parsedResult).toEqual({
        output: 'command output',
        exitCode: 0,
      });
    });

    it('should handle command execution errors', async () => {
      const errorMessage = 'Command execution failed';
      const mockConnect = vi.fn();
      const mockExecuteCommand = vi.fn().mockRejectedValue(new Error(errorMessage));
      const mockDisconnect = vi.fn();

      (SSHManager as Mock).mockImplementation(() => ({
        connect: mockConnect,
        executeCommand: mockExecuteCommand,
        disconnect: mockDisconnect,
      }));

      remoteShellAction = new RemoteShellAction(mockEnv);
      await expect(remoteShellAction.execute(validInput)).rejects.toThrow(errorMessage);

      expect(mockConnect).toHaveBeenCalled();
      expect(mockExecuteCommand).toHaveBeenCalledWith(validInput.command);
      expect(mockDisconnect).toHaveBeenCalled();
    });

    it('should handle connection errors', async () => {
      const errorMessage = 'Connection failed';
      const mockConnect = vi.fn().mockRejectedValue(new Error(errorMessage));
      const mockExecuteCommand = vi.fn();
      const mockDisconnect = vi.fn();

      (SSHManager as Mock).mockImplementation(() => ({
        connect: mockConnect,
        executeCommand: mockExecuteCommand,
        disconnect: mockDisconnect,
      }));

      remoteShellAction = new RemoteShellAction(mockEnv);
      await expect(remoteShellAction.execute(validInput)).rejects.toThrow(errorMessage);

      expect(mockConnect).toHaveBeenCalled();
      expect(mockExecuteCommand).not.toHaveBeenCalled();
      expect(mockDisconnect).toHaveBeenCalled();
    });

    it('should validate input before execution', async () => {
      remoteShellAction = new RemoteShellAction(mockEnv);
      const invalidInput = { ...validInput, port: undefined };
      
      await expect(remoteShellAction.execute(invalidInput as any)).rejects.toThrow();
    });
  });
});
