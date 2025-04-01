import { z } from 'zod';
import { HyperbolicAction } from './hyperbolic-action';
import { SSHManager } from '../utils/ssh-manager';

const REMOTE_SHELL_PROMPT = `
This tool will execute a command on the remote server via SSH.
It takes the following inputs:
- host: The hostname or IP address of the remote machine
- username: The username to connect with
- password: (Optional) The password for authentication
- privateKey: (Optional) The private key content for authentication
- privateKeyPath: (Optional) Path to the private key file for authentication
- port: The SSH port number
- command: The shell command to execute

Note: Either password or privateKey/privateKeyPath must be provided for authentication.
`;

const RemoteShellSchema = z.object({
  host: z.string().min(1),
  username: z.string().min(1),
  password: z.string().optional(),
  privateKey: z.string().optional(),
  privateKeyPath: z.string().optional(),
  port: z.number().int().min(1).max(65535),
  command: z.string().min(1),
}).strict().refine(
  (data) => data.password || data.privateKey || data.privateKeyPath,
  {
    message: 'Either password, privateKey, or privateKeyPath must be provided',
  }
);

export type RemoteShellInput = z.infer<typeof RemoteShellSchema>;

/**
 * Action class for remote shell execution
 */
export class RemoteShellAction extends HyperbolicAction<RemoteShellInput> {
  private sshManager: SSHManager | null = null;

  constructor(_env: Record<string, string>) {
    super(
      'remote_shell',
      REMOTE_SHELL_PROMPT,
      RemoteShellSchema,
      (args: RemoteShellInput) => this.execute(args)
    );
  }

  protected validateInput(input: RemoteShellInput): RemoteShellInput {
    return RemoteShellSchema.parse(input);
  }

  async execute(args: RemoteShellInput): Promise<string> {
    const input = this.validateInput(args);
    
    try {
      this.sshManager = new SSHManager({
        host: input.host,
        username: input.username,
        password: input.password,
        privateKey: input.privateKey,
        privateKeyPath: input.privateKeyPath,
        port: input.port,
      });

      await this.sshManager.connect();

      try {
        const result = await this.sshManager.executeCommand(input.command);
        return JSON.stringify({
          output: result.output,
          exitCode: result.exitCode,
        });
      } finally {
        await this.sshManager.disconnect();
      }
    } catch (error) {
      if (this.sshManager) {
        await this.sshManager.disconnect();
      }
      throw error;
    }
  }
}
