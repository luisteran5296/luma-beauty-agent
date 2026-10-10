import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowRight, ArrowUp, Check, ChevronDown, Leaf, Menu, Minus, Plus, Search, ShoppingBag, SlidersHorizontal, Sparkles, Star, X} from 'lucide-react';
import {catalog, chat, type Product, type CatalogResponse} from './api';
import {AgentAvatar} from './AgentAvatar';
import './style.css';

const dollars = (n:number) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n);
type CartLine = {product:Product; quantity:number};
type Message = {role:'user'|'assistant'; text:string; products?:Product[]};

function ProductImage({product}:{product:Product}) {
  const [failed,setFailed] = useState(false);
  return failed ? <div className="image-fallback"><Leaf size={40}/><span>Image unavailable</span></div> : <img src={product.image_urls[0]} alt={product.title} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>;
}

function ProductCard({product,onOpen,onAdd}:{product:Product;onOpen:(p:Product)=>void;onAdd:(p:Product)=>void}) {
  return <article className="product-card"><button className="product-photo" onClick={()=>onOpen(product)} aria-label={`View ${product.title}`}><ProductImage product={product}/><span className="product-category">{product.category}</span></button><div className="product-info"><p className="brand">{product.brand || 'Beauty collection'}</p><button className="product-title" onClick={()=>onOpen(product)}>{product.title}</button><div className="rating"><Star size={13} fill="currentColor"/>{product.rating === null ? 'Not yet rated' : `${product.rating.toFixed(1)} · ${product.review_count?.toLocaleString() ?? 'Unknown'} ratings`}</div><div className="price-row"><strong>{dollars(product.price_usd)}</strong><button className="add-button" onClick={()=>onAdd(product)} aria-label={`Add ${product.title} to bag`}><Plus size={18}/></button></div><button className="catalog-add" onClick={()=>onAdd(product)}>Add to cart</button></div></article>;
}

function App() {
  const [data,setData] = useState<CatalogResponse>({products:[],total:0,version:'',categories:[]});
  const [query,setQuery] = useState(''); const [category,setCategory] = useState(''); const [maxPrice,setMaxPrice] = useState('');
  const [loading,setLoading] = useState(true); const [error,setError] = useState('');
  const [selected,setSelected] = useState<Product|null>(null); const [cartOpen,setCartOpen] = useState(false); const [checkedOut,setCheckedOut] = useState(false);
  const [cart,setCart] = useState<CartLine[]>(()=>{try {return JSON.parse(localStorage.getItem('luma-bag')||'[]');} catch {return [];}});
  const [chatOpen,setChatOpen] = useState(false); const [messages,setMessages] = useState<Message[]>([]); const [input,setInput] = useState('');
  const [busy,setBusy] = useState(false); const [status,setStatus] = useState(''); const [chatError,setChatError] = useState(''); const [remaining,setRemaining] = useState(10);
  const session = useRef(sessionStorage.getItem('luma-session') || crypto.randomUUID()); const controller = useRef<AbortController|null>(null); const chatEnd = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const agentDialogRef = useRef<HTMLDialogElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const agentOrigin = useRef<HTMLElement|null>(null);
  const agentOriginBounds = useRef<DOMRect|null>(null);
  const modalAnimation = useRef<Animation|null>(null);
  const modalClosing = useRef(false);
  const count = cart.reduce((sum,line)=>sum+line.quantity,0); const total = cart.reduce((sum,line)=>sum+line.product.price_usd*line.quantity,0);
  useEffect(()=>{localStorage.setItem('luma-bag',JSON.stringify(cart));},[cart]);
  useEffect(()=>{sessionStorage.setItem('luma-session',session.current); return ()=>controller.current?.abort();},[]);
  useEffect(()=>{let active=true; const refresh=(initial=false)=>{if(initial)setLoading(true); catalog(query,category,maxPrice).then(value=>{if(active){setData(value);setError('');}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});}; const timer=setTimeout(()=>refresh(true),250); const interval=setInterval(()=>refresh(),30000); return ()=>{active=false;clearTimeout(timer);clearInterval(interval);};},[query,category,maxPrice]);
  useEffect(()=>{if(selected || cartOpen) dialogRef.current?.showModal(); else dialogRef.current?.close();},[selected,cartOpen]);
  useEffect(()=>{
    const modal=agentDialogRef.current;
    if(chatOpen && modal && !modal.open){
      modal.showModal();
      modal.dataset.phase='opening';
      if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
        const origin=agentTransform(modal);
        const animation=modal.animate([{transform:origin,opacity:0},{transform:'translate(0,0) scale(1)',opacity:1}],{duration:360,easing:'cubic-bezier(.2,.8,.2,1)'});
        modalAnimation.current=animation;
        animation.onfinish=()=>{modal.dataset.phase='open';modalAnimation.current=null;};
      } else modal.dataset.phase='open';
    } else if(!chatOpen && modal?.open)modal.close();
  },[chatOpen]);
  useEffect(()=>()=>{modalAnimation.current?.cancel();},[]);
  useEffect(()=>{if(!chatOpen)return; const previous=document.body.style.overflow; document.body.style.overflow='hidden'; return ()=>{document.body.style.overflow=previous;};},[chatOpen]);
  useEffect(()=>{if(!chatOpen)agentOrigin.current?.focus();},[chatOpen]);
  useEffect(()=>{if(chatOpen && !busy && !selected && !cartOpen)chatInputRef.current?.focus();},[chatOpen,busy,selected,cartOpen,data.total]);
  useEffect(()=>{chatEnd.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[messages,busy,chatOpen]);
  function add(product:Product) {setCheckedOut(false);setCart(lines=>{const found=lines.find(line=>line.product.id===product.id);return found ? lines.map(line=>line.product.id===product.id ? {...line,quantity:Math.min(10,line.quantity+1)} : line) : [...lines,{product,quantity:1}];});}
  function quantity(id:string,delta:number) {setCart(lines=>lines.map(line=>line.product.id===id ? {...line,quantity:Math.min(10,line.quantity+delta)} : line).filter(line=>line.quantity>0));}
  function closeDialog() {setSelected(null);setCartOpen(false);}
  function agentTransform(modal:HTMLDialogElement) {
    const liveBounds=agentOrigin.current?.getBoundingClientRect();
    const destination=liveBounds?.width ? liveBounds : agentOriginBounds.current;
    const box=modal.getBoundingClientRect();
    const x=destination ? destination.x+destination.width/2 : window.innerWidth-70;
    const y=destination ? destination.y+destination.height/2 : window.innerHeight-45;
    return `translate(${x-(box.x+box.width/2)}px,${y-(box.y+box.height/2)}px) scale(.08)`;
  }
  function openAgent() {
    if(chatOpen || modalClosing.current)return;
    agentOrigin.current=document.activeElement instanceof HTMLElement ? document.activeElement : null;
    agentOriginBounds.current=agentOrigin.current?.getBoundingClientRect() || null;
    setChatOpen(true);
  }
  function closeAgent() {
    const modal=agentDialogRef.current;
    if(!modal?.open || modalClosing.current)return;
    modalClosing.current=true;
    const currentStyle=getComputedStyle(modal);
    const fromTransform=currentStyle.transform, fromOpacity=currentStyle.opacity;
    modalAnimation.current?.cancel();
    const finish=()=>{modal.close();setChatOpen(false);modalClosing.current=false;modalAnimation.current=null;agentOrigin.current?.focus();};
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){finish();return;}
    modal.dataset.phase='closing';
    const animation=modal.animate([{transform:fromTransform,opacity:fromOpacity},{transform:agentTransform(modal),opacity:0}],{duration:260,easing:'cubic-bezier(.4,0,.8,.2)',fill:'forwards'});
    modalAnimation.current=animation;
    animation.onfinish=()=>{finish();animation.cancel();};
  }
  function trapAgentFocus(event:React.KeyboardEvent<HTMLDialogElement>) {
    if(event.key!=='Tab')return;
    const controls=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]')).filter(el=>el.getClientRects().length>0);
    const first=controls[0], last=controls[controls.length-1];
    if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
  }
  async function send(text=input) {
    if(!text.trim() || busy || !remaining)return;
    openAgent();setInput('');setChatError('');setBusy(true);setMessages(items=>[...items,{role:'user',text:text.trim()}]);
    controller.current = new AbortController(); let answer = ''; let cards:Product[]=[];
    try {
      await chat(text.trim(),session.current,(kind,value)=>{
        if(kind==='status')setStatus(value.message);
        if(kind==='answer')answer=value.text;
        if(kind==='recommendations')cards=value.products;
        if(kind==='error'){setChatError(value.message);if(typeof value.turns_remaining==='number')setRemaining(value.turns_remaining);}
        if(kind==='done'){setRemaining(value.turns_remaining);setMessages(items=>[...items,{role:'assistant',text:answer,products:cards}]);}
      },controller.current.signal);
    } catch(e) {setChatError(e instanceof Error ? e.message : 'Could not reach the assistant.');}
    finally {setBusy(false);setStatus('');}
  }
  return <>
    <div className="demo-store-banner"><span className="demo-label">DEMO STORE</span><p>This is a fake store for exploring AI shopping. No real purchases, payments, or deliveries.</p></div>
    <header className="header"><a href="#" className="logo" aria-label="Luma home">luma<span>beauty marketplace</span></a><div className="delivery-note"><span>Explore your next</span><strong>Beauty favorite</strong></div><label className="search header-search"><span className="search-department">Beauty</span><input aria-label="Search products" placeholder="Search skincare, brands and more" value={query} onChange={e=>setQuery(e.target.value)}/><button aria-label="Search catalog" onClick={()=>document.getElementById('collection')?.scrollIntoView()}><Search size={22}/></button></label><button className="header-guide" onClick={openAgent}><span>Need a hand?</span><strong>Ask your AI guide</strong></button><button className="bag-button" onClick={()=>{setSelected(null);setCartOpen(true);setCheckedOut(false);}} aria-label={`Open shopping bag, ${count} items`}><ShoppingBag size={29}/><b>{count}</b><span>Cart</span></button></header>
    <nav className="market-nav" aria-label="Departments"><a href="#collection"><Menu size={18}/> All beauty</a><button onClick={()=>{setCategory('');setQuery('moisturizer');}}>Moisturizers</button><button onClick={()=>{setCategory('');setQuery('cleanser');}}>Cleansers</button><button onClick={()=>{setCategory('');setQuery('serum');}}>Serums</button><button onClick={()=>{setCategory('');setQuery('sunscreen');}}>Sun care</button><button onClick={openAgent}><Sparkles size={15}/> Shopping assistant</button><span>DEMO · NO REAL ORDERS</span></nav>
    <main>
      <section className="market-hero agent-hero"><div className="agent-hero-copy"><span className="eyebrow"><Sparkles size={14}/> MEET YOUR AI SHOPPING AGENT</span><h1>A little conversation.<br/><span>A better beauty routine.</span></h1><p>Meet Luma, your AI beauty guide. Tell it about your skin, preferences, and budget to get feedback and compare products from our 100-product collection.</p><div className="agent-hero-actions"><button className="button agent-primary" onClick={openAgent}>Talk to Luma <ArrowRight size={17}/></button><a className="agent-browse" href="#collection">Or browse the collection <ArrowRight size={15}/></a></div><span className="hero-agent-note">AI-generated guidance · Real product data · Demo shopping</span></div><div className="hero-agent-preview"><div className="orb-stage"><AgentAvatar size={200}/><span className="orb-spark spark-one">✦</span><span className="orb-spark spark-two">✧</span></div><span className="agent-identity">Luma <span>AI AGENT</span></span><div className="agent-presence"><span/> Here to help you find your fit</div><button className="hero-suggestion" onClick={()=>{openAgent();setInput('Help me find a moisturizer under $30');}}><span>“Help me find a moisturizer under $30”</span><ArrowUp size={15}/></button></div></section>
      <div className="snapshot-strip"><span><Check size={15}/> Real catalog products</span><span><Star size={15}/> Aggregate shopper ratings</span><span><Sparkles size={15}/> Advice from catalog evidence</span></div>
      <div className="catalog-layout"><aside className="department-sidebar"><h3>Department</h3><button className={!category?'active':''} onClick={()=>setCategory('')}>All skin care</button>{data.categories.map(c=><button className={category===c?'active':''} key={c} onClick={()=>setCategory(c)}>{c}</button>)}<h3>Shop by budget</h3>{[['','Any price'],['15','Under $15'],['30','Under $30'],['50','Under $50']].map(([value,label])=><button key={label} className={maxPrice===value?'active':''} onClick={()=>setMaxPrice(value)}>{label}</button>)}<div className="sidebar-guide"><Sparkles size={22}/><strong>Your beauty guide</strong><p>Have a question? Get help comparing products in this collection.</p><button className="button primary" onClick={openAgent}>Ask the guide</button></div></aside>
      <section id="collection" className="collection"><div className="section-top"><div><p className="eyebrow">FIND YOUR EVERYDAY FAVORITES</p><h2>Skin care & everyday beauty</h2></div><span className="collection-count">{data.total ? `${data.total} products to explore` : 'The collection is taking shape'}</span></div><div className="filter-bar"><label className="select-wrap"><SlidersHorizontal size={16}/><select aria-label="Product category" value={category} onChange={e=>setCategory(e.target.value)}><option value="">All categories</option>{data.categories.map(c=><option key={c}>{c}</option>)}</select><ChevronDown size={14}/></label><label className="select-wrap"><select aria-label="Maximum price" value={maxPrice} onChange={e=>setMaxPrice(e.target.value)}><option value="">Any budget</option><option value="15">Under $15</option><option value="30">Under $30</option><option value="50">Under $50</option></select><ChevronDown size={14}/></label></div>
      {loading ? <div className="loading-state" role="status"><span className="spinner"/> Gathering the collection…</div> : error ? <div className="empty-state" role="alert"><h3>A moment, please.</h3><p>{error}</p><button className="button secondary" onClick={()=>window.location.reload()}>Try again</button></div> : !data.total ? <div className="empty-state"><div className="empty-icon"><Leaf size={30}/></div><span className="eyebrow">REAL PRODUCTS, THOUGHTFULLY COLLECTED</span><h3>A good collection takes a little care.</h3><p>Our real beauty catalog is awaiting import. Once it’s ready, you’ll find products, prices, and personalized recommendations here.</p><span className="small-note">Product collection pending · No sample products are listed</span></div> : !data.products.length ? <div className="empty-state"><h3>No matches just yet.</h3><p>Try another search or give your budget a little more room.</p><button className="button secondary" onClick={()=>{setQuery('');setCategory('');setMaxPrice('');}}>Clear filters</button></div> : <div className="product-grid">{data.products.map(p=><ProductCard key={p.id} product={p} onOpen={setSelected} onAdd={add}/>)}</div>}
      <p className="price-note">Amazon US prices and ratings are historical 2023 dataset snapshots, not current offers. Prices shown in USD. This demo does not place orders.</p></section></div>
      <section className="guide-banner"><div className="guide-symbol"><Sparkles size={28}/></div><div><p className="eyebrow">A LITTLE HELP GOES A LONG WAY</p><h2>Not sure where to start?</h2><p>Tell your guide about your preferences and budget. We’ll help narrow the collection.</p></div><button className="button primary" onClick={openAgent}>Let’s find your fit <ArrowRight size={17}/></button></section>
    </main><footer><a href="#" className="logo">luma<span>BEAUTY, CONSIDERED</span></a><p>A shopping experiment, made with care.<br/>Simulated purchases. No payments or orders.</p><span>© {new Date().getFullYear()} Luma</span></footer>
    <button className={`chat-launcher ${chatOpen?'hidden':''}`} onClick={openAgent}><AgentAvatar size={38}/><span>Ask Luma <small>AI shopping agent</small></span><Sparkles size={15}/></button>
    <dialog ref={agentDialogRef} className="agent-modal" aria-labelledby="agent-modal-title" aria-describedby="agent-modal-description" onKeyDown={trapAgentFocus} onCancel={e=>{e.preventDefault();closeAgent();}} onClose={()=>setChatOpen(false)} onClick={e=>{if(e.target===agentDialogRef.current)closeAgent();}}>
      <div className="agent-experience"><aside className="agent-identity-panel"><span className="agent-wordmark">luma<span>YOUR AI BEAUTY GUIDE</span></span><div className="modal-orb-stage"><AgentAvatar busy={busy} size={170}/></div><span className="ai-label"><Sparkles size={12}/> AI SHOPPING AGENT</span><h2>A guide that starts<br/>with you.</h2><p>Tell me what matters to your routine. I’ll search the collection and help you compare your options.</p><div className="agent-state" role="status"><span className={busy?'thinking-dot':''}/>{busy?'Thinking through your request':'Ready when you are'}</div><div className="agent-facts"><span><Check size={14}/> 100 real catalog products</span><span><Check size={14}/> Your preferences, your budget</span><span><Check size={14}/> Clear comparisons</span></div><span className="agent-text-note">Text chat · No microphone access</span></aside>
      <section className="agent-chat"><div className="chat-header"><div className="mobile-agent-avatar"><AgentAvatar busy={busy} size={46}/></div><div><div className="modal-heading"><strong id="agent-modal-title">Talk to Luma</strong><span className="ai-header-badge">AI AGENT</span></div><p id="agent-modal-description">Your personal space to explore beauty.</p></div><button className="icon-button" aria-label="Close beauty guide" onClick={closeAgent}><X size={21}/></button></div>
      <div className="chat-content" role="log" aria-label="Conversation with Luma">{messages.length===0 && <div className="guide-welcome"><span className="welcome-icon"><Sparkles size={23}/></span><p className="eyebrow">LET’S FIND WHAT FITS YOU</p><h3>What would you like<br/>a little help with?</h3><p>Start with your skin needs, a product question, or a budget. I’ll take it from there.</p><div className="prompt-chips">{['A simple skincare routine under $30','Help me compare moisturizers','Find a gift for a beauty lover'].map(prompt=><button disabled={busy || !data.total || remaining===0} key={prompt} onClick={()=>send(prompt)}><Sparkles size={13}/><span>{prompt}</span><ArrowRight size={15}/></button>)}</div></div>}{!data.total && <div className="catalog-notice">The catalog is awaiting import. Your shopping guide will be ready when real products are loaded.</div>}{messages.map((m,i)=><div key={i} className={`message ${m.role}`}><span className="message-author">{m.role==='assistant'?'Luma · AI agent':'You'}</span><p>{m.text}</p>{m.products?.map(p=><button className="chat-product" key={p.id} onClick={()=>setSelected(p)}><ProductImage product={p}/><span>{p.title}<strong>{dollars(p.price_usd)}</strong></span><ArrowRight size={16}/></button>)}</div>)}{busy && <div className="chat-status" role="status"><span className="thinking-dots"><i/><i/><i/></span>{status || 'Luma is thinking…'}</div>}{chatError && <p className="chat-error" role="alert">{chatError}</p>}<div ref={chatEnd}/></div>
      <div className="agent-composer"><form className="chat-form" onSubmit={e=>{e.preventDefault();send();}}><label className="sr-only" htmlFor="chat-input">Message your beauty guide</label><textarea ref={chatInputRef} id="chat-input" rows={2} placeholder="Tell Luma what you’re looking for…" maxLength={1200} value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter' && !e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault();send();}}} disabled={busy || !data.total || remaining===0}/><button aria-label="Send message" disabled={busy || !data.total || !input.trim() || remaining===0}><ArrowUp size={19}/></button></form><div className="chat-footnote">{remaining} messages remaining · Advice grounded in our catalog</div><p className="ai-disclaimer">Luma is an AI agent and can make mistakes. Prices are 2023 snapshots. This is a demo store.</p></div></section></div>
    </dialog>
    <dialog ref={dialogRef} aria-label={selected?'Product details':'Shopping bag'} onCancel={closeDialog} onClick={e=>{if(e.target===dialogRef.current)closeDialog();}}><button className="dialog-close icon-button" onClick={closeDialog} aria-label="Close dialog"><X size={22}/></button>{selected && <div className="product-detail"><div className="detail-image"><ProductImage product={selected}/></div><div><p className="eyebrow">{selected.brand || selected.category}</p><h2>{selected.title}</h2><p className="detail-price">{dollars(selected.price_usd)}</p><p>{selected.description}</p><p className="small-note">{selected.rating===null?'Rating unavailable':`${selected.rating} / 5 · ${selected.review_count ?? 'Unknown'} ratings`}<br/>Imported {new Date(selected.collected_at).toLocaleDateString('en-US')}{selected.source_snapshot ? ` · Source snapshot: ${selected.source_snapshot}` : ''}</p><button className="button primary" onClick={()=>add(selected)}>Add to demo bag <Plus size={17}/></button><a className="source-link" href={selected.source_url} target="_blank" rel="noreferrer">View original product source ↗</a></div></div>}{cartOpen && <div className="bag-dialog"><p className="eyebrow">YOUR EVERYDAY EDIT</p><h2>Your bag<span>.</span></h2>{checkedOut ? <div className="checkout-success"><Check size={32}/><h3>Your demo routine is ready.</h3><p>This was a simulated checkout. No payment was taken and no order was placed.</p><button className="button primary" onClick={closeDialog}>Keep exploring</button></div> : !cart.length ? <div className="empty-bag"><ShoppingBag size={32}/><h3>Room for your next favorite.</h3><p>Your bag is empty.</p></div> : <>{cart.map(line=><div className="bag-line" key={line.product.id}><ProductImage product={line.product}/><div><strong>{line.product.title}</strong><span>{dollars(line.product.price_usd)}</span><div className="quantity-controls"><button aria-label={`Remove one ${line.product.title}`} onClick={()=>quantity(line.product.id,-1)}><Minus size={14}/></button><span>{line.quantity}</span><button aria-label={`Add one ${line.product.title}`} onClick={()=>quantity(line.product.id,1)}><Plus size={14}/></button></div></div><button className="icon-button" aria-label={`Remove ${line.product.title} from bag`} onClick={()=>setCart(lines=>lines.filter(x=>x.product.id!==line.product.id))}><X size={18}/></button></div>)}<div className="bag-total"><span>Demo total</span><strong>{dollars(total)}</strong></div><button className="button primary checkout" onClick={()=>{setCheckedOut(true);setCart([]);}}>Simulate checkout <ArrowRight size={17}/></button><p className="small-note">No payment information required. This does not place an order.</p></>}</div>}</dialog>
  </>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
