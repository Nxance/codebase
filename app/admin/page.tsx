import {getAppUser} from '../../lib/app-user';
import {redirect} from 'next/navigation';
import {chatGPTSignInPath} from '../chatgpt-auth';
import AccessNotice from '../access-notice';
import AdminPanel from './panel';
import './admin.css';
export const dynamic='force-dynamic';
export default async function Admin(){let user;try{user=await getAppUser();}catch{return <AccessNotice title="Temporarily unavailable" message="We could not load the admin panel. Please refresh to try again."/>;}if(!user)redirect(chatGPTSignInPath('/admin'));if(user.status!=='active'||user.role!=='admin')return <AccessNotice title="Administrator access required" message="This account does not have permission to manage Nxance users or their saved data."/>;return <AdminPanel viewer={{id:user.userId,name:user.displayName,isOwner:user.isOwner}}/>;}
