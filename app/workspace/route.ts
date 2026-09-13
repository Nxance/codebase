import {chatGPTSignInPath} from '../chatgpt-auth';
import {getAppUser} from '../../lib/app-user';
import html from './workspace.html?raw';
export const dynamic='force-dynamic';
export async function GET(){try{const user=await getAppUser();if(!user)return new Response(null,{status:303,headers:{Location:chatGPTSignInPath('/workspace'),'Cache-Control':'no-store'}});if(user.status!=='active')return new Response(null,{status:303,headers:{Location:'/','Cache-Control':'no-store'}});return new Response(html,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'}});}catch{return new Response('Account services are temporarily unavailable. Please refresh to try again.',{status:503,headers:{'Cache-Control':'no-store'}});}}
