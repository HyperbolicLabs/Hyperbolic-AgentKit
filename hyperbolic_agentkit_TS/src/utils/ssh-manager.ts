import { Client, ClientChannel } from 'ssh2';
import { APIError } from '../errors/base';
import { readFileSync } from 'fs';

export interface SSHConfig {
  host: string;
  username: string;
  password?: string;
  privateKey?: string;
  privateKeyPath?: string;
  port: number;
}

export interface CommandResult {
  output: string;
  exitCode: number;
}

/**
 * Manages SSH connections and command execution
 */
export class SSHManager {
  private client: Client;
  private channel: ClientChannel | null = null;

  constructor(config: SSHConfig) {
    this.client = new Client();
    this.config = config;
  }

  private config: SSHConfig;

  /**
   * Connects to a remote server via SSH
   */
  async connect(): Promise<void> {
    try {
      const config = {
        host: this.config.host,
        username: this.config.username,
        password: this.config.password,
        privateKey: this.config.privateKey || (this.config.privateKeyPath ? readFileSync(this.config.privateKeyPath) : undefined),
        port: this.config.port
      };

      await new Promise<void>((resolve, reject) => {
        this.client.on('ready', () => {
          resolve();
        }).on('error', (err: Error) => {
          reject(err);
        });

        this.client.connect(config);
      });
    } catch (error) {
      throw new APIError(`SSH connection failed: ${(error as Error).message}`);
    }
  }

  /**
   * Executes a command on the remote server
   */
  async executeCommand(command: string): Promise<CommandResult> {
    if (!this.client) {
      throw new APIError('SSH client not initialized');
    }

    try {
      return await new Promise<CommandResult>((resolve, reject) => {
        this.client.exec(command, (err: Error | undefined, channel: ClientChannel) => {
          if (err) {
            reject(new APIError(`Command execution failed: ${err.message}`));
            return;
          }

          let output = '';
          let exitCode = 0;

          channel.on('data', (data: Buffer) => {
            output += data.toString();
          });

          channel.stderr.on('data', (data: Buffer) => {
            output += data.toString();
          });

          channel.on('close', (code: number) => {
            exitCode = code;
            resolve({ output, exitCode });
          });

          channel.on('error', (err: Error) => {
            reject(new APIError(`Command execution failed: ${err.message}`));
          });
        });
      });
    } catch (error) {
      throw new APIError(`Command execution failed: ${(error as Error).message}`);
    }
  }

  /**
   * Disconnects from the remote server
   */
  disconnect(): void {
    if (this.channel) {
      this.channel.close();
      this.channel = null;
    }
    this.client.end();
  }
}
