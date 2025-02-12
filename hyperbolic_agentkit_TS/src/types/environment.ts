import { z } from 'zod';

/**
 * Environment schema for validating environment variables
 */
export const EnvironmentSchema = z.object({
  ANTHROPIC_API_KEY: z.string().min(1, 'ANTHROPIC_API_KEY is required'),
  OPENAI_API_KEY: z.string().optional(),
  HYPERBOLIC_API_KEY: z.string().min(1, 'HYPERBOLIC_API_KEY is required'),
  CDP_API_KEY_NAME: z.string().min(1, 'CDP_API_KEY_NAME is required'),
  CDP_API_KEY_PRIVATE_KEY: z.string().min(1, 'CDP_API_KEY_PRIVATE_KEY is required'),
  TWITTER_API_KEY: z.string().min(1, 'TWITTER_API_KEY is required'),
  TWITTER_API_SECRET: z.string().min(1, 'TWITTER_API_SECRET is required'),
  TWITTER_ACCESS_TOKEN: z.string().min(1, 'TWITTER_ACCESS_TOKEN is required'),
  TWITTER_ACCESS_TOKEN_SECRET: z.string().min(1, 'TWITTER_ACCESS_TOKEN_SECRET is required'),
  SSH_PRIVATE_KEY_PATH: z.string().min(1, 'SSH_PRIVATE_KEY_PATH is required'),
  LANGCHAIN_TRACING_V2: z.preprocess((val) => {
    if (typeof val === 'string') {
      return val.toLowerCase() === 'true';
    }
    return val;
  }, z.boolean().optional()),
  LANGCHAIN_ENDPOINT: z.string().min(1, 'LANGCHAIN_ENDPOINT is required'),
  LANGCHAIN_API_KEY: z.string().min(1, 'LANGCHAIN_API_KEY is required'),
  LANGCHAIN_PROJECT: z.string().min(1, 'LANGCHAIN_PROJECT is required')
});

export type Environment = z.infer<typeof EnvironmentSchema>;

/**
 * Validates environment variables
 * @param env Partial environment object to validate
 * @returns Validated environment object
 * @throws {Error} If validation fails
 */
export function validateEnvironment(env: Partial<Environment>): Environment {
  try {
    return EnvironmentSchema.parse(env);
  } catch (error) {
    if (error instanceof z.ZodError) {
      const errors = error.errors.map(err => err.message).join('\n');
      throw new Error(`Environment validation failed:\n${errors}`);
    }
    throw error;
  }
}

/**
 * Gets environment variables from process.env
 * @returns Environment object
 */
export function getEnvironment(): Environment {
  const env: Partial<Environment> = {
    ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
    OPENAI_API_KEY: process.env.OPENAI_API_KEY,
    HYPERBOLIC_API_KEY: process.env.HYPERBOLIC_API_KEY,
    CDP_API_KEY_NAME: process.env.CDP_API_KEY_NAME,
    CDP_API_KEY_PRIVATE_KEY: process.env.CDP_API_KEY_PRIVATE_KEY,
    TWITTER_API_KEY: process.env.TWITTER_API_KEY,
    TWITTER_API_SECRET: process.env.TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN: process.env.TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET: process.env.TWITTER_ACCESS_TOKEN_SECRET,
    SSH_PRIVATE_KEY_PATH: process.env.SSH_PRIVATE_KEY_PATH,
    LANGCHAIN_TRACING_V2: process.env.LANGCHAIN_TRACING_V2 === 'true',
    LANGCHAIN_ENDPOINT: process.env.LANGCHAIN_ENDPOINT,
    LANGCHAIN_API_KEY: process.env.LANGCHAIN_API_KEY,
    LANGCHAIN_PROJECT: process.env.LANGCHAIN_PROJECT
  };

  return validateEnvironment(env);
}
