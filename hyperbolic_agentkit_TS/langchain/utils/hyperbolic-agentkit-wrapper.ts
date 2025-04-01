import { getEnvironmentVariable } from "@langchain/core/utils/env";

/**
 * Wrapper for Hyperbolic Agentkit Core.
 */
export class HyperbolicAgentkitWrapper {
  hyperbolicApiKey: string;

  constructor(fields?: { hyperbolicApiKey?: string }) {
    const apiKey = fields?.hyperbolicApiKey ?? 
      getEnvironmentVariable("HYPERBOLIC_API_KEY");
    
    if (!apiKey) {
      throw new Error(
        "Hyperbolic API Key not found. Please set HYPERBOLIC_API_KEY environment variable or pass it in the constructor."
      );
    }

    this.hyperbolicApiKey = apiKey;
  }

  /**
   * Run a Hyperbolic Action.
   * @param func The function to run
   * @param args The arguments to pass to the function
   * @returns The result of the function call
   */
  async runAction(
    func: (...args: any[]) => Promise<string>,
    args: Record<string, any>
  ): Promise<string> {
    return await func(args);
  }
}
