import { env } from 'cloudflare:workers';
export function getDb(){if(!env.DB)throw new Error('Workspace storage unavailable');return env.DB;}
export async function loadWorkspace(userId:string){return getDb().prepare('SELECT state_json, revision, updated_at FROM workspaces WHERE user_id = ?').bind(userId).first<{state_json:string;revision:number;updated_at:string}>();}
