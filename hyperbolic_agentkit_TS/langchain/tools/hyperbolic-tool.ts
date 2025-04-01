import { Tool, ToolParams } from "@langchain/core/tools";
import { z } from "zod";
import { CallbackManagerForToolRun } from "@langchain/core/callbacks/manager";
import { RunnableConfig } from "@langchain/core/runnables";
import { HyperbolicAgentkitWrapper } from "../utils/hyperbolic-agentkit-wrapper";

/**
 * Exception raised when a command execution times out.
 */
class CommandTimeout extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CommandTimeout";
  }
}

type ToolInputSchema = z.ZodEffects<
  z.ZodObject<
    { input: z.ZodOptional<z.ZodString> },
    "strip",
    z.ZodTypeAny,
    { input?: string },
    { input?: string }
  >,
  string | undefined,
  { input?: string }
>;

const DEFAULT_SCHEMA: ToolInputSchema = z
  .object({
    input: z.string().optional().describe("The input to the tool"),
  })
  .strip()
  .transform((obj) => obj.input);

const createToolSchema = (schema: z.ZodObject<any>): ToolInputSchema => {
  return schema.strip().transform((obj) => obj.input) as ToolInputSchema;
};

interface HyperbolicToolParams extends ToolParams {
  schema?: z.ZodObject<any>;
}

/**
 * Tool for interacting with the Hyperbolic SDK.
 */
export class HyperbolicTool extends Tool {
  public name: string;
  public description: string;
  private readonly hyperbolicAgentkitWrapper: HyperbolicAgentkitWrapper;
  private readonly func: (...args: any[]) => Promise<string>;
  private readonly timeoutSeconds = 10;
  private readonly customSchema?: z.ZodObject<any>;

  constructor(
    hyperbolicAgentkitWrapper: HyperbolicAgentkitWrapper,
    toolName: string,
    toolDescription: string,
    func: (...args: any[]) => Promise<string>,
    schema?: z.ZodObject<any>
  ) {
    const params: HyperbolicToolParams = {
      verbose: true
    };
    super(params);
    
    this.name = toolName;
    this.description = toolDescription;
    this.hyperbolicAgentkitWrapper = hyperbolicAgentkitWrapper;
    this.func = func;
    this.customSchema = schema;
    
    this.schema = schema ? createToolSchema(schema) : DEFAULT_SCHEMA;
  }

  /** @ignore */
  protected async _call(
    args: Record<string, any>,
    runManager?: CallbackManagerForToolRun,
    config?: RunnableConfig
  ): Promise<string> {
    let parsedInputArgs: Record<string, any>;
    if (this.customSchema) {
      parsedInputArgs = this.customSchema.parse(args);
    } else {
      const input = args.input || "";
      parsedInputArgs = { instructions: input };
    }

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        reject(
          new CommandTimeout(
            `Command timed out after ${this.timeoutSeconds} seconds`
          )
        );
      }, this.timeoutSeconds * 1000);

      this.hyperbolicAgentkitWrapper
        .runAction(this.func, parsedInputArgs)
        .then((result) => {
          clearTimeout(timeoutId);
          resolve(result);
        })
        .catch((error) => {
          clearTimeout(timeoutId);
          reject(error);
        });
    });
  }
}
