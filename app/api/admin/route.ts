import {z} from 'zod';
import {getAppUser} from '../../../lib/app-user';
import {getDb,loadWorkspace} from '../../../db';
import {json,trustedWrite} from '../../../lib/api-security';
import {workspaceInput} from '../../../lib/workspace-validation';
export const dynamic='force-dynamic';
const id=z.string().min(1).max(200);
const inputSchema=z.discriminatedUnion('action',[
 z.object({action:z.literal('access'),userId:id,role:z.enum(['user','admin']),status:z.enum(['active','suspended']),accessRevision:z.number().int().min(1)}),
 z.object({action:z.literal('workspace'),userId:id,revision:z.number().int().min(0),state:workspaceInput.shape.state}),
 z.object({action:z.literal('reset'),userId:id,revision:z.number().int().min(1)})
]);
type Target={user_id:string;role:string;status:string;access_revision:number};
export async function GET(request:Request){try{
 const admin=await getAppUser();if(!admin)return json({error:'Sign in to continue.'},401);if(admin.role!=='admin'||admin.status!=='active')return json({error:'Administrator access is required.'},403);
 const db=getDb(),url=new URL(request.url),mode=url.searchParams.get('mode')||'users',page=Math.max(1,Math.min(100000,Number(url.searchParams.get('page'))||1)),offset=(Math.floor(page)-1)*25;
 const owner=(await db.prepare("SELECT value FROM app_settings WHERE key='owner_user_id'").first<{value:string}>())?.value??'';
 if(mode==='user'){
  const userId=url.searchParams.get('id');if(!userId||userId.length>200)return json({error:'Select a valid user.'},400);
  const user=await db.prepare('SELECT * FROM app_users WHERE user_id=?').bind(userId).first();if(!user)return json({error:'User not found.'},404);if(!admin.isOwner&&user.user_id!==admin.userId&&(user.role==='admin'||user.user_id===owner))return json({error:'Only the owner can inspect another administrator’s saved workspace.'},403);const record=await loadWorkspace(userId);
  return json({user:{...user,isOwner:userId===owner},state:record?JSON.parse(record.state_json):null,revision:record?.revision??0,updatedAt:record?.updated_at??null});
 }
 if(mode==='database'){
  const [users,workspaces,audit,unlinked]=await db.batch<{count:number}>([db.prepare('SELECT COUNT(*) AS count FROM app_users'),db.prepare('SELECT COUNT(*) AS count FROM workspaces'),db.prepare('SELECT COUNT(*) AS count FROM admin_audit'),db.prepare('SELECT COUNT(*) AS count FROM workspaces w LEFT JOIN app_users u ON u.user_id=w.user_id WHERE u.user_id IS NULL')]);
  return json({users:users.results[0].count,workspaces:workspaces.results[0].count,audit:audit.results[0].count,unlinked:unlinked.results[0].count});
 }
 if(mode==='audit'){
  const entries=await db.prepare('SELECT a.*,actor.email AS actor_email,target.email AS target_email FROM admin_audit a LEFT JOIN app_users actor ON actor.user_id=a.actor_id LEFT JOIN app_users target ON target.user_id=a.target_id ORDER BY a.id DESC LIMIT 25 OFFSET ?').bind(offset).all();const total=await db.prepare('SELECT COUNT(*) AS count FROM admin_audit').first<{count:number}>();return json({entries:entries.results,total:total?.count??0,page});
 }
 if(mode!=='users')return json({error:'Unknown view.'},400);
 const q=(url.searchParams.get('q')||'').slice(0,150).toLowerCase(),like='%'+q.replace(/[!%_]/g,'!$&')+'%';
 const rows=await db.prepare("SELECT u.*,w.revision AS workspace_revision,w.updated_at AS workspace_updated_at FROM app_users u LEFT JOIN workspaces w ON w.user_id=u.user_id WHERE lower(u.email) LIKE ? ESCAPE '!' OR lower(u.display_name) LIKE ? ESCAPE '!' ORDER BY u.joined_at DESC,u.user_id LIMIT 25 OFFSET ?").bind(like,like,offset).all();
 const total=await db.prepare("SELECT COUNT(*) AS count FROM app_users WHERE lower(email) LIKE ? ESCAPE '!' OR lower(display_name) LIKE ? ESCAPE '!'").bind(like,like).first<{count:number}>();
 const stats=await db.prepare("SELECT COUNT(*) AS total,SUM(status='active') AS active,SUM(status='suspended') AS suspended,SUM(role='admin') AS admins FROM app_users").first();
 return json({users:rows.results.map(u=>({...u,isOwner:u.user_id===owner})),total:total?.count??0,page,stats,viewer:{id:admin.userId,isOwner:admin.isOwner}});
 }catch{console.error('Admin read failed');return json({error:'The admin panel is temporarily unavailable. Please try again.'},503);}}
export async function POST(request:Request){try{
 const admin=await getAppUser();if(!admin)return json({error:'Sign in to continue.'},401);if(admin.role!=='admin'||admin.status!=='active')return json({error:'Administrator access is required.'},403);if(!trustedWrite(request,'admin'))return json({error:'This request could not be verified.'},403);
 let input:z.infer<typeof inputSchema>;try{const text=await request.text();if(text.length>50000)return json({error:'Request too large.'},413);input=inputSchema.parse(JSON.parse(text));}catch{return json({error:'Check the entered values and try again.'},400);}
 const db=getDb(),target=await db.prepare('SELECT user_id,role,status,access_revision FROM app_users WHERE user_id=?').bind(input.userId).first<Target>();if(!target)return json({error:'User not found.'},404);
 const owner=(await db.prepare("SELECT value FROM app_settings WHERE key='owner_user_id'").first<{value:string}>())?.value;
 if(input.action==='access'&&(target.user_id===owner||target.user_id===admin.userId))return json({error:'You cannot change your own access or the owner account.'},403);
 if(!admin.isOwner&&(target.role==='admin'||target.user_id===owner||(input.action==='access'&&input.role==='admin')))return json({error:'Only the owner can manage administrators.'},403);
 const now=new Date().toISOString();let statement;let detail:string;
 if(input.action==='access'){
  if(input.accessRevision!==target.access_revision)return json({error:'This account changed. Reopen it to review the latest status.'},409);
  statement=db.prepare('UPDATE app_users SET role=?,status=?,access_revision=access_revision+1 WHERE user_id=? AND access_revision=?').bind(input.role,input.status,input.userId,input.accessRevision);detail=JSON.stringify({role:input.role,status:input.status});
 }else{
  const state=input.action==='reset'?{holdings:[],sampleMode:false,goal:{target:2500000,savings:0,years:10,rate:8}}:input.state;
  statement=input.revision===0?db.prepare('INSERT INTO workspaces (user_id,state_json,revision,updated_at) VALUES (?,?,1,?) ON CONFLICT(user_id) DO NOTHING').bind(input.userId,JSON.stringify(state),now):db.prepare('UPDATE workspaces SET state_json=?,revision=revision+1,updated_at=? WHERE user_id=? AND revision=?').bind(JSON.stringify(state),now,input.userId,input.revision);
  detail=JSON.stringify({revision:input.revision+1,holdingCount:state.holdings.length});
 }
 const audit=db.prepare('INSERT INTO admin_audit (actor_id,target_id,action,detail,created_at) SELECT ?,?,?,?,? WHERE changes()>0').bind(admin.userId,input.userId,input.action,detail,now);
 const result=await db.batch([statement,audit]);if(!result[0].meta.changes)return json({error:'This record changed in another session. Reopen it before trying again.'},409);return json({ok:true});
 }catch{console.error('Admin change failed');return json({error:'The change could not be saved. Please try again.'},503);}}
