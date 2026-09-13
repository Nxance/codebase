import { z } from 'zod';
const amount=z.number().finite().min(0).max(1e11);
export const workspaceInput=z.object({revision:z.number().int().min(0).max(2147483646),state:z.object({holdings:z.array(z.object({name:z.string().trim().max(100),type:z.enum(['Equity','Debt','Gold','Cash','Other']),value:amount})).max(100),sampleMode:z.boolean(),goal:z.object({target:amount.positive(),savings:amount,years:z.number().int().min(1).max(50),rate:z.number().finite().min(0).max(30)})})});
