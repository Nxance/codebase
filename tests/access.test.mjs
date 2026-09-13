import {build} from 'esbuild';
import {DatabaseSync} from 'node:sqlite';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
const sqlite=new DatabaseSync(':memory:');
for(const file of readdirSync('drizzle').filter(f=>f.endsWith('.sql')).sort())sqlite.exec(readFileSync('drizzle/'+file,'utf8'));
function prepared(sql,args=[]){return {bind(...values){return prepared(sql,values);},async first(){return sqlite.prepare(sql).get(...args)??null;},async all(){try{return {results:sqlite.prepare(sql).all(...args)};}catch(e){console.error('SQL test failure:',sql,e.message);throw e;}},async run(){if(/^\s*SELECT/i.test(sql))return {results:sqlite.prepare(sql).all(...args),meta:{changes:0}};const result=sqlite.prepare(sql).run(...args);return {results:[],meta:{changes:Number(result.changes)}};}};}
globalThis.testDb={prepare:prepared,async batch(statements){sqlite.exec('BEGIN');try{const result=[];for(const s of statements)result.push(await s.run());sqlite.exec('COMMIT');return result;}catch(e){sqlite.exec('ROLLBACK');throw e;}}};
globalThis.testEnv={NXANCE_OWNER_EMAIL:'owner@example.test'};
async function compile(entry){const out=await build({entryPoints:[entry],bundle:true,write:false,format:'esm',platform:'node',plugins:[{name:'mock-platform',setup(b){
 b.onResolve({filter:/lib\/app-user$/},()=>({path:'actor',namespace:'mock'}));
 b.onResolve({filter:/chatgpt-auth$/},()=>({path:'identity',namespace:'mock'}));
 b.onResolve({filter:/\/db$/},()=>({path:'db',namespace:'mock'}));
 b.onResolve({filter:/^cloudflare:workers$/},()=>({path:'env',namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},({path})=>({contents:path==='actor'?'export async function getAppUser(){return globalThis.testActor;}':path==='identity'?'export async function getChatGPTUser(){return globalThis.testIdentity;}':path==='env'?'export const env=globalThis.testEnv;':"export function getDb(){return globalThis.testDb;} export async function loadWorkspace(id){return getDb().prepare('SELECT state_json,revision,updated_at FROM workspaces WHERE user_id=?').bind(id).first();}"}));
}}]});return import('data:text/javascript;base64,'+Buffer.from(out.outputFiles[0].text).toString('base64'));}
const appUser=await compile('lib/app-user.ts'),adminApi=await compile('app/api/admin/route.ts'),workspaceApi=await compile('app/api/workspace/route.ts');
async function signIn(id,email){globalThis.testIdentity={userId:id,email,displayName:email,fullName:null};return appUser.getAppUser();}
const member=await signIn('member','member@example.test');assert.equal(member.role,'user');assert.equal(member.isOwner,false);
assert.equal(sqlite.prepare("SELECT COUNT(*) AS n FROM app_settings").get().n,0);
const owner=await signIn('owner','owner@example.test');assert.equal(owner.role,'admin');assert.equal(owner.isOwner,true);
const duplicate=await signIn('not-owner','owner@example.test');assert.equal(duplicate.isOwner,false);assert.equal(duplicate.role,'user');
const second=await signIn('second','second@example.test');
function request(body,admin=true,origin='https://nxance.test'){return new Request('https://nxance.test/api/'+(admin?'admin':'workspace'),{method:admin?'POST':'PUT',headers:{'Content-Type':'application/json','X-Nxance-Request':admin?'admin':'save',origin,'Sec-Fetch-Site':origin==='https://nxance.test'?'same-origin':'cross-site'},body:JSON.stringify(body)});}
const state={holdings:[{name:'Cash',type:'Cash',value:1000}],sampleMode:false,goal:{target:12000,savings:1000,years:1,rate:0}};
globalThis.testActor=null;assert.equal((await adminApi.GET(new Request('https://nxance.test/api/admin'))).status,401);assert.equal((await workspaceApi.GET()).status,401);
globalThis.testActor=member;assert.equal((await adminApi.GET(new Request('https://nxance.test/api/admin'))).status,403);assert.equal((await adminApi.POST(request({action:'reset',userId:'second',revision:1}))).status,403);
assert.equal((await workspaceApi.PUT(request({state,revision:0,userId:'second'},false))).status,200);assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM workspaces WHERE user_id=?').get('second').n,0);
globalThis.testActor=second;assert.equal((await workspaceApi.GET()).status,200);assert.equal((await (await workspaceApi.GET()).json()).state,null);
globalThis.testActor=owner;
let users=await (await adminApi.GET(new Request('https://nxance.test/api/admin'))).json();assert.equal(users.total,4);assert.ok(users.users.find(u=>u.user_id==='owner').isOwner);
assert.equal((await (await adminApi.GET(new Request('https://nxance.test/api/admin?q='+encodeURIComponent("' OR 1=1--")))).json()).total,0);
assert.equal((await adminApi.POST(request({action:'access',userId:'member',role:'user',status:'suspended',accessRevision:1},true,'https://evil.test'))).status,403);
assert.equal((await adminApi.POST(request({action:'access',userId:'owner',role:'user',status:'suspended',accessRevision:1}))).status,403);
assert.equal((await adminApi.POST(request({action:'access',userId:'member',role:'user',status:'suspended',accessRevision:1}))).status,200);
const suspended=await signIn('member','member@example.test');assert.equal(suspended.status,'suspended');globalThis.testActor=suspended;assert.equal((await workspaceApi.GET()).status,403);assert.equal((await workspaceApi.PUT(request({state,revision:1},false))).status,403);assert.equal((await adminApi.GET(new Request('https://nxance.test/api/admin'))).status,403);
globalThis.testActor=owner;assert.equal((await adminApi.POST(request({action:'access',userId:'member',role:'user',status:'active',accessRevision:2}))).status,200);
const countBefore=sqlite.prepare('SELECT COUNT(*) AS n FROM admin_audit').get().n;
assert.equal((await adminApi.POST(request({action:'workspace',userId:'member',revision:1,state:{...state,holdings:[{name:'Cash',type:'Cash',value:2000}]}}))).status,200);
assert.equal(sqlite.prepare('SELECT revision FROM workspaces WHERE user_id=?').get('member').revision,2);
assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM admin_audit').get().n,countBefore+1);
assert.equal((await adminApi.POST(request({action:'workspace',userId:'member',revision:1,state}))).status,409);assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM admin_audit').get().n,countBefore+1);
assert.equal((await adminApi.POST(request({action:'workspace',userId:'member',revision:2,state:{...state,holdings:[{name:'Bad',type:'Cash',value:-1}]}}))).status,400);
assert.equal((await adminApi.POST(request({action:'reset',userId:'member',revision:2}))).status,200);
assert.equal(sqlite.prepare('SELECT revision FROM workspaces WHERE user_id=?').get('member').revision,3);
assert.deepEqual(JSON.parse(sqlite.prepare('SELECT state_json FROM workspaces WHERE user_id=?').get('member').state_json).holdings,[]);
globalThis.testActor=await signIn('member','member@example.test');assert.equal((await workspaceApi.PUT(request({state,revision:2},false))).status,409);
globalThis.testActor=owner;assert.equal((await adminApi.POST(request({action:'access',userId:'second',role:'admin',status:'active',accessRevision:1}))).status,200);
const delegated=await signIn('second','second@example.test');assert.equal(delegated.role,'admin');globalThis.testActor=delegated;
assert.equal((await adminApi.GET(new Request('https://nxance.test/api/admin?mode=user&id=owner'))).status,403);
assert.equal((await adminApi.POST(request({action:'access',userId:'member',role:'admin',status:'active',accessRevision:3}))).status,403);
assert.equal((await adminApi.POST(request({action:'workspace',userId:'owner',revision:0,state}))).status,403);
assert.equal((await adminApi.GET(new Request('https://nxance.test/api/admin?mode=database'))).status,200);
assert.ok((await (await adminApi.GET(new Request('https://nxance.test/api/admin?mode=audit'))).json()).entries.length>0);
console.log('Passed: owner binding, non-admin denial, private workspaces, suspension enforcement, CSRF, admin delegation, protected owner, validation, revision conflicts, reset, SQL queries and transactional audit records.');
