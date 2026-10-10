import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously } from 'firebase/auth';

export type Product = {id:string; title:string; brand:string|null; description:string; category:string; image_urls:string[]; source_url:string; price_usd:number; price_mxn:number|null; source?:'amazon_mx'|'amazon_us_2023'|'walmart_us'; price_source_usd?:string|null; source_snapshot?:string|null; rating:number|null; review_count:number|null; collected_at:string};
export type CatalogResponse = {products:Product[]; total:number; version:string; categories:string[]};
const base = import.meta.env.VITE_API_BASE || '';
let authPromise: Promise<string> | undefined;

async function token() {
  if (import.meta.env.DEV && import.meta.env.VITE_LOCAL_DEV_AUTH === 'true') return '';
  const apiKey = import.meta.env.VITE_FIREBASE_API_KEY;
  if (!apiKey) throw new Error('Shopping assistant is awaiting cloud configuration.');
  if (!authPromise) authPromise = (async () => {
    const app = initializeApp({apiKey, authDomain:'sitiosweb1.firebaseapp.com', projectId:'sitiosweb1', appId:import.meta.env.VITE_FIREBASE_APP_ID});
    const auth = getAuth(app);
    if (!auth.currentUser) await signInAnonymously(auth);
    return auth.currentUser!.getIdToken();
  })().catch(error => {authPromise = undefined; throw error;});
  await authPromise;
  // Firebase refreshes expired tokens on subsequent requests.
  return getAuth().currentUser!.getIdToken();
}

export async function catalog(query='', category='', maxPrice=''):Promise<CatalogResponse> {
  const params = new URLSearchParams({q:query});
  if (category) params.set('category', category);
  if (maxPrice) params.set('max_price',maxPrice);
  const response = await fetch(`${base}/api/products?${params}`, {signal:AbortSignal.timeout(15000)});
  if (!response.ok) throw new Error('The collection could not be loaded. Please try again.');
  return response.json();
}

export async function chat(message:string, sessionId:string, onEvent:(kind:string,data:any)=>void, signal:AbortSignal) {
  const accessToken = await token();
  const response = await fetch(`${base}/api/chat`, {method:'POST', signal, headers:{'Content-Type':'application/json', ...(accessToken ? {Authorization:`Bearer ${accessToken}`} : {})}, body:JSON.stringify({message, session_id:sessionId, request_id:crypto.randomUUID()})});
  if (!response.ok) {
    const error = await response.json().catch(()=>({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : 'The assistant is unavailable.');
  }
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const {done,value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value,{stream:true}).replace(/\r\n/g,'\n');
    let split;
    while ((split = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0,split); buffer = buffer.slice(split+2);
      const kind = frame.split('\n').find(line=>line.startsWith('event: '))?.slice(7);
      const data = frame.split('\n').filter(line=>line.startsWith('data: ')).map(line=>line.slice(6)).join('\n');
      if (kind && data) onEvent(kind,JSON.parse(data));
    }
  }
}
