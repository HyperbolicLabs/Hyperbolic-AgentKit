import { z } from 'zod';

/**
 * Base interface for all action arguments
 */
export interface BaseActionArgs {
  [key: string]: unknown;
}

/**
 * Type for the action function
 */
export type ActionFunction<T extends BaseActionArgs = BaseActionArgs> = (args: T) => Promise<string>;

/**
 * Base class for all Hyperbolic actions
 */
export class HyperbolicAction<T extends BaseActionArgs = BaseActionArgs> {
  constructor(
    public readonly name: string,
    public readonly description: string,
    public readonly argsSchema: z.ZodType<T> | null,
    public readonly func: ActionFunction<T>
  ) {}

  /**
   * Validates the input arguments against the schema and executes the action
   * @param args The input arguments for the action
   * @returns A promise that resolves to the action result
   * @throws {ValidationError} If the arguments fail validation
   */
  async execute(args: T): Promise<string> {
    if (this.argsSchema) {
      try {
        this.argsSchema.parse(args);
      } catch (error) {
        if (error instanceof z.ZodError) {
          throw new ValidationError(`Invalid arguments: ${error.message}`);
        }
        throw error;
      }
    }
    return await this.func(args);
  }
}

// Re-export error for convenience
import { ValidationError } from '../errors/base';
