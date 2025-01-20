import { z } from "zod";

export interface HyperbolicAction {
  name: string;
  description: string;
  execute: (...args: any[]) => Promise<string>;
  schema?: z.ZodObject<any>;
}

export const HYPERBOLIC_ACTIONS: Record<string, HyperbolicAction> = {
  // Add your actions here
};
