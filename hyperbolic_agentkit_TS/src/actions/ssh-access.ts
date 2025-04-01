import { z } from 'zod';
import { HyperbolicAction } from './hyperbolic-action';
import { SSHManager } from '../utils/ssh-manager';

const SSH_ACCESS_PROMPT = `
This tool will establish an SSH connection to a remote machine.
It takes the following inputs:
- host: The hostname or IP address of the remote machine
- username: The username to connect with
- password: (Optional) The password for authentication
- privateKey: (Optional) The private key content for authentication
- privateKeyPath: (Optional) Path to the private key file for authentication
- port: The SSH port number

Note: Either password or privateKey/privateKeyPath must be provided for authentication.
`;

/**
 * Input schema for SSH access
 */
const SSHAccessInputSchema = z.object({
  host: z.string().describe('The hostname or IP address of the remote machine'),
  username: z.string().describe('The username to connect with'),
  password: z.string().optional().describe('The password for authentication'),
  privateKey: z.string().optional().describe('The private key content for authentication'),
  privateKeyPath: z.string().optional().describe('Path to the private key file for authentication'),
  port: z.number().int().min(1).max(65535).describe('The SSH port number')
}).strict().refine(
  data => data.password !== undefined || data.privateKey !== undefined || data.privateKeyPath !== undefined,
  { message: 'Either password or privateKey/privateKeyPath must be provided' }
);

export type SSHAccessInput = z.infer<typeof SSHAccessInputSchema>;

/**
 * Action class for SSH access
 */
export class SSHAccessAction extends HyperbolicAction<SSHAccessInput> {
  private sshManager: SSHManager | null = null;

  constructor(_env: Record<string, string>) {
    super(
      'ssh_access',
      SSH_ACCESS_PROMPT,
      SSHAccessInputSchema,
      (args: SSHAccessInput) => this.execute(args)
    );
  }

  protected validateInput(input: SSHAccessInput): SSHAccessInput {
    return SSHAccessInputSchema.parse(input);
  }

  async execute(input: SSHAccessInput): Promise<string> {
    const config = this.validateInput(input);
    
    try {
      this.sshManager = new SSHManager({
        host: config.host,
        username: config.username,
        password: config.password,
        privateKey: config.privateKey,
        privateKeyPath: config.privateKeyPath,
        port: config.port
      });

      await this.sshManager.connect();
      return `Successfully established SSH connection to ${config.host}`;
    } catch (error) {
      return `Failed to establish SSH connection: ${(error as Error).message}`;
    } finally {
      if (this.sshManager) {
        await this.sshManager.disconnect();
      }
    }
  }
}
