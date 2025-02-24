import { Tool } from "@langchain/core/tools";
import { HyperbolicTool } from "../tools/hyperbolic-tool";
import { HyperbolicAgentkitWrapper } from "../utils/hyperbolic-agentkit-wrapper";
import { HYPERBOLIC_ACTIONS, HyperbolicAction } from "../../src/actions";

/**
 * Hyperbolic Platform Toolkit.
 *
 * Security Note: This toolkit contains tools that can read and modify
 * the state of a service; e.g., by creating, deleting, or updating,
 * reading underlying data.
 *
 * For example, this toolkit can be used to rent compute, check GPU status,
 * and manage compute resources on Hyperbolic supported infrastructure.
 */
export class HyperbolicToolkit {
  private readonly tools: Tool[];

  constructor(private readonly hyperbolicAgentkitWrapper: HyperbolicAgentkitWrapper) {
    this.tools = this.loadTools();
  }

  /**
   * Get the tools in the toolkit.
   * @returns Array of tools
   */
  getTools(): Tool[] {
    return this.tools;
  }

  /**
   * Create a toolkit from a HyperbolicAgentkitWrapper instance.
   * @param hyperbolicAgentkitWrapper The wrapper instance
   * @returns HyperbolicToolkit instance
   */
  static fromHyperbolicAgentkitWrapper(
    hyperbolicAgentkitWrapper: HyperbolicAgentkitWrapper
  ): HyperbolicToolkit {
    return new HyperbolicToolkit(hyperbolicAgentkitWrapper);
  }

  /**
   * Load all available Hyperbolic tools.
   * @returns Array of Tool instances
   */
  private loadTools(): Tool[] {
    return Object.entries(HYPERBOLIC_ACTIONS).map(([name, action]: [string, HyperbolicAction]) => {
      return new HyperbolicTool(
        this.hyperbolicAgentkitWrapper,
        name,
        action.description || "",
        action.execute.bind(action),
        action.schema
      );
    });
  }
}
