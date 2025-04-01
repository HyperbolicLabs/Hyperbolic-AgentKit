import { ConfigurationError } from '../errors/base';
import { Environment } from '../types/environment';

/**
 * Get the Hyperbolic API key from environment variables
 * @param env The environment object
 * @returns The API key
 * @throws {ConfigurationError} If HYPERBOLIC_API_KEY is not set in environment variables
 */
export function getApiKey(env: Partial<Environment>): string {
  const apiKey = env.HYPERBOLIC_API_KEY;
  if (!apiKey) {
    throw new ConfigurationError('HYPERBOLIC_API_KEY environment variable is not set');
  }
  return apiKey;
}

/**
 * Get all required API keys and configuration from environment variables
 * @param env The environment object
 * @returns Object containing all required API keys and configuration
 * @throws {ConfigurationError} If any required environment variables are missing
 */
export function getApiConfig(env: Partial<Environment>): {
  hyperbolicApiKey: string;
  cdpApiKeyName: string;
  cdpApiKeyPrivateKey: string;
  twitterApiKey: string;
  twitterApiSecret: string;
  twitterAccessToken: string;
  twitterAccessTokenSecret: string;
} {
  const hyperbolicApiKey = getApiKey(env);
  const cdpApiKeyName = env.CDP_API_KEY_NAME;
  const cdpApiKeyPrivateKey = env.CDP_API_KEY_PRIVATE_KEY;
  const twitterApiKey = env.TWITTER_API_KEY;
  const twitterApiSecret = env.TWITTER_API_SECRET;
  const twitterAccessToken = env.TWITTER_ACCESS_TOKEN;
  const twitterAccessTokenSecret = env.TWITTER_ACCESS_TOKEN_SECRET;

  if (!cdpApiKeyName || !cdpApiKeyPrivateKey) {
    throw new ConfigurationError('CDP API key configuration is missing');
  }

  if (!twitterApiKey || !twitterApiSecret || !twitterAccessToken || !twitterAccessTokenSecret) {
    throw new ConfigurationError('Twitter API configuration is missing');
  }

  return {
    hyperbolicApiKey,
    cdpApiKeyName,
    cdpApiKeyPrivateKey,
    twitterApiKey,
    twitterApiSecret,
    twitterAccessToken,
    twitterAccessTokenSecret,
  };
}
