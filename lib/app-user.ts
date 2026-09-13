import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '../app/chatgpt-auth';
import {getDb} from '../db';
export type AppUser={userId:string;email:string;displayName:string;fullName:string|null;role:'admin'|'user';status:'active'|'suspended';isOwner:boolean;accessRevision:number};
export async function getAppUser():Promise<AppUser|null>{
 const identity=await getChatGPTUser();if(!identity)return null;const db=getDb(),now=new Date().toISOString();
 let owner=await db.prepare("SELECT value FROM app_settings WHERE key='owner_user_id'").first<{value:string}>();
 const ownerEmail=(env as unknown as {NXANCE_OWNER_EMAIL?:string}).NXANCE_OWNER_EMAIL?.trim().toLowerCase();
 if(!owner&&ownerEmail&&identity.email.trim().toLowerCase()===ownerEmail){await db.prepare("INSERT INTO app_settings (key,value) VALUES ('owner_user_id',?) ON CONFLICT(key) DO NOTHING").bind(identity.userId).run();owner=await db.prepare("SELECT value FROM app_settings WHERE key='owner_user_id'").first<{value:string}>();}
 const isOwner=owner?.value===identity.userId;
 await db.prepare("INSERT INTO app_users (user_id,email,display_name,role,status,joined_at,last_seen_at,access_revision) VALUES (?,?,?,?,?,?,?,1) ON CONFLICT(user_id) DO UPDATE SET email=excluded.email,display_name=excluded.display_name,last_seen_at=excluded.last_seen_at,role=CASE WHEN ? THEN 'admin' ELSE app_users.role END,status=CASE WHEN ? THEN 'active' ELSE app_users.status END").bind(identity.userId,identity.email,identity.displayName,isOwner?'admin':'user','active',now,now,isOwner?1:0,isOwner?1:0).run();
 const row=await db.prepare('SELECT role,status,access_revision FROM app_users WHERE user_id=?').bind(identity.userId).first<{role:'admin'|'user';status:'active'|'suspended';access_revision:number}>();if(!row)throw Error('Account unavailable');
 return {...identity,isOwner,role:isOwner?'admin':row.role,status:isOwner?'active':row.status,accessRevision:row.access_revision};
}
