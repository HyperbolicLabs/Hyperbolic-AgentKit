import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SSHManager, SSHConfig, CommandResult } from '../../src/utils/ssh-manager';
import { Client, ClientChannel } from 'ssh2';
import { EventEmitter } from 'events';

// Create a mock Client class
class MockClient extends EventEmitter {
  connect: any;
  exec: any;
  end: any;

  constructor() {
    super();
    this.connect = vi.fn((config) => {
      setTimeout(() => this.emit('ready'), 0);
      return this;
    });
    this.exec = vi.fn((command, callback) => {
      const channel = new EventEmitter() as ClientChannel;
      channel.stderr = new EventEmitter();
      callback(undefined, channel);
      setTimeout(() => {
        channel.emit('data', Buffer.from('test output'));
        channel.stderr.emit('data', Buffer.from('test error'));
        channel.emit('close', 0);
      }, 0);
    });
    this.end = vi.fn();
  }
}

// Mock the ssh2 Client
vi.mock('ssh2', () => {
  return {
    Client: vi.fn().mockImplementation(() => new MockClient()),
  };
});

describe('SSHManager', () => {
  let sshManager: SSHManager;
  const config: SSHConfig = {
    host: 'test-host',
    username: 'test-user',
    password: 'test-password',
    port: 22,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(Client).mockClear();
    sshManager = new SSHManager(config);
  });

  describe('connect', () => {
    it('should connect successfully with password', async () => {
      await expect(sshManager.connect()).resolves.not.toThrow();
    });

    it('should connect successfully with private key', async () => {
      const configWithKey: SSHConfig = {
        ...config,
        password: undefined,
        privateKey: 'test-private-key',
      };
      sshManager = new SSHManager(configWithKey);
      await expect(sshManager.connect()).resolves.not.toThrow();
    });

    it('should handle connection errors', async () => {
      const mockClient = new MockClient();
      mockClient.connect = vi.fn().mockImplementation(() => {
        process.nextTick(() => mockClient.emit('error', new Error('Connection failed')));
        return mockClient;
      });
      vi.mocked(Client).mockImplementation(() => mockClient);

      sshManager = new SSHManager(config);
      await expect(sshManager.connect()).rejects.toThrow('SSH connection failed');
    });
  });

  describe('executeCommand', () => {
    it('should execute command successfully', async () => {
      const mockClient = new MockClient();
      vi.mocked(Client).mockImplementation(() => mockClient);

      sshManager = new SSHManager(config);
      await sshManager.connect();
      const result = await sshManager.executeCommand('test command');
      expect(result).toEqual({
        output: 'test outputtest error',
        exitCode: 0,
      });
    });

    it('should handle command execution errors', async () => {
      const mockClient = new MockClient();
      mockClient.exec = vi.fn().mockImplementation((command, callback) => {
        callback(new Error('Command execution failed'), {} as ClientChannel);
      });
      vi.mocked(Client).mockImplementation(() => mockClient);

      sshManager = new SSHManager(config);
      await sshManager.connect();
      await expect(sshManager.executeCommand('test command')).rejects.toThrow('Command execution failed');
    });
  });

  describe('disconnect', () => {
    it('should disconnect successfully', async () => {
      await sshManager.connect();
      sshManager.disconnect();
      expect(vi.mocked(Client).mock.results[0].value.end).toHaveBeenCalled();
    });
  });
});
