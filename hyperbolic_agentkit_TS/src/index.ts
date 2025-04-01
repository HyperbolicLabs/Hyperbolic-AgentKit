// Export base types and interfaces
export * from './types/environment';

// Export error types
export * from './errors/base';

// Export utilities
export * from './utils/api';
export * from './utils/ssh-manager';

// Export actions
export * from './actions/hyperbolic-action';
export * from './actions/get-available-gpus';
export * from './actions/get-gpu-status';
export * from './actions/rent-compute';
export * from './actions/terminate-compute';
export * from './actions/ssh-access';
export * from './actions/remote-shell';
export * from './actions/get-current-balance';
export * from './actions/get-spend-history';

// Create action instances
import { SSHAccessAction } from './actions/ssh-access';
import { RemoteShellAction } from './actions/remote-shell';
import { GetAvailableGpusAction } from './actions/get-available-gpus';
import { GetGpuStatusAction } from './actions/get-gpu-status';
import { RentComputeAction } from './actions/rent-compute';
import { TerminateComputeAction } from './actions/terminate-compute';
import { GetCurrentBalanceAction } from './actions/get-current-balance';
import { GetSpendHistoryAction } from './actions/get-spend-history';

/**
 * Create all Hyperbolic actions with the provided environment
 * @param env The environment object containing API keys and configuration
 * @returns An object containing all initialized actions
 */
export class HyperbolicAgentKit {
  private sshAccess: SSHAccessAction;
  private remoteShell: RemoteShellAction;
  private getAvailableGpus: GetAvailableGpusAction;
  private getGpuStatus: GetGpuStatusAction;
  private rentCompute: RentComputeAction;
  private terminateCompute: TerminateComputeAction;
  private getCurrentBalance: GetCurrentBalanceAction;
  private getSpendHistory: GetSpendHistoryAction;

  constructor(env: Record<string, string>) {
    this.sshAccess = new SSHAccessAction(env);
    this.remoteShell = new RemoteShellAction(env);
    this.getAvailableGpus = new GetAvailableGpusAction(env);
    this.getGpuStatus = new GetGpuStatusAction(env);
    this.rentCompute = new RentComputeAction(env);
    this.terminateCompute = new TerminateComputeAction(env);
    this.getCurrentBalance = new GetCurrentBalanceAction(env);
    this.getSpendHistory = new GetSpendHistoryAction(env);
  }

  async sshAccessAction(input: Parameters<SSHAccessAction['execute']>[0]): Promise<string> {
    return await this.sshAccess.execute(input);
  }

  async remoteShellAction(input: Parameters<RemoteShellAction['execute']>[0]): Promise<string> {
    return await this.remoteShell.execute(input);
  }

  async getAvailableGpusAction(): Promise<string> {
    return await this.getAvailableGpus.execute({});
  }

  async getGpuStatusAction(input: Parameters<GetGpuStatusAction['execute']>[0]): Promise<string> {
    return await this.getGpuStatus.execute(input);
  }

  async rentComputeAction(input: Parameters<RentComputeAction['execute']>[0]): Promise<string> {
    return await this.rentCompute.execute(input);
  }

  async terminateComputeAction(input: Parameters<TerminateComputeAction['execute']>[0]): Promise<string> {
    return await this.terminateCompute.execute(input);
  }

  async getCurrentBalanceAction(): Promise<string> {
    return await this.getCurrentBalance.execute({});
  }

  async getSpendHistoryAction(): Promise<string> {
    return await this.getSpendHistory.execute({});
  }
}

export {
  SSHAccessAction,
  RemoteShellAction,
  GetAvailableGpusAction,
  GetGpuStatusAction,
  RentComputeAction,
  TerminateComputeAction,
  GetCurrentBalanceAction,
  GetSpendHistoryAction
};
