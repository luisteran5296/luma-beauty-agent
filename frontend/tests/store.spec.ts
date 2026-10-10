import {test,expect} from '@playwright/test';
const product={id:'B000000001',title:'Test-only moisturizer',brand:'Test fixture',description:'Fixture for browser tests only.',category:'Skin Care',image_urls:['https://example.com/test.jpg'],source_url:'https://www.amazon.com.mx/dp/B000000001',price_usd:10,price_mxn:180,rating:null,review_count:null,collected_at:'2026-10-09T12:00:00Z'};

test('empty real catalog and guide on mobile',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[],total:0,version:'test',categories:[]}}));
  await page.goto('/');
  await expect(page.getByText('A good collection takes a little care.')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.locator('.chat-launcher').click();
  await expect(page.getByLabel('Message your beauty guide')).toBeDisabled();
  await page.getByRole('button',{name:'Close beauty guide'}).click();
});

test('product detail, bag, quantities, and simulated checkout',async({page})=>{
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[product],total:1,version:'test',categories:['Skin Care']}}));
  await page.goto('/');
  await page.getByRole('button',{name:`View ${product.title}`,exact:true}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button',{name:'Add to demo bag'}).click();
  await page.getByRole('button',{name:'Close dialog'}).click();
  await page.getByRole('button',{name:'Open shopping bag, 1 items'}).click();
  await page.getByRole('button',{name:`Add one ${product.title}`}).click();
  await expect(page.getByText('$20.00',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Simulate checkout'}).click();
  await expect(page.getByText('This was a simulated checkout. No payment was taken and no order was placed.')).toBeVisible();
});

test('filter query reaches backend and no-match state',async({page})=>{
  await page.route('**/api/products?*',route=>{
    const query=new URL(route.request().url()).searchParams.get('q');
    return route.fulfill({json:{products:query?[ ]:[product],total:1,version:'test',categories:['Skin Care']}});
  });
  await page.goto('/');
  await page.getByLabel('Search products').fill('no-matching-product');
  await expect(page.getByText('No matches just yet.')).toBeVisible();
  await page.getByRole('button',{name:'Clear filters'}).click();
  await expect(page.getByRole('button',{name:`View ${product.title}`,exact:true})).toBeVisible();
});

test('chat accepts streamed answer and canonical recommendation cards',async({page})=>{
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[product],total:1,version:'test',categories:['Skin Care']}}));
  await page.route('**/api/chat',route=>route.fulfill({contentType:'text/event-stream',body:
    'event: status\ndata: {"message":"Searching fixture catalog"}\n\n'+
    'event: answer\ndata: {"text":"A test-only assistant response."}\n\n'+
    `event: recommendations\ndata: ${JSON.stringify({products:[product]})}\n\n`+
    'event: done\ndata: {"turns_remaining":9}\n\n'}));
  await page.goto('/');
  await expect(page.getByRole('button',{name:`View ${product.title}`,exact:true})).toBeVisible();
  await page.locator('.chat-launcher').click();
  await page.getByLabel('Message your beauty guide').fill('Find a moisturizer under $15');
  await page.getByRole('button',{name:'Send message'}).click();
  await expect(page.getByText('A test-only assistant response.')).toBeVisible();
  await expect(page.getByText('9 messages remaining · Advice grounded in our catalog')).toBeVisible();
  await page.locator('.chat-product').click();
  await expect(page.getByRole('dialog',{name:'Product details'})).toBeVisible();
  await page.getByRole('button',{name:'Close dialog'}).click();
  await expect(page.getByRole('dialog',{name:'Talk to Luma'})).toBeVisible();
  await expect(page.getByText('A test-only assistant response.')).toBeVisible();
});

test('AI hero opens a centered accessible modal and restores focus on Escape',async({page})=>{
  await page.setViewportSize({width:1440,height:1000});
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[product],total:1,version:'test',categories:['Skin Care']}}));
  await page.goto('/');
  await expect(page.getByText('This is a fake store for exploring AI shopping. No real purchases, payments, or deliveries.')).toBeVisible();
  const trigger=page.getByRole('button',{name:'Talk to Luma',exact:true});
  await trigger.click();
  const modal=page.getByRole('dialog',{name:'Talk to Luma'});
  await expect(modal).toBeVisible();
  await expect(modal).toHaveAttribute('data-phase','open');
  const bounds=await modal.boundingBox();
  expect(Math.abs(bounds!.x+bounds!.width/2-720)).toBeLessThan(2);
  await expect(page.getByLabel('Message your beauty guide')).toBeFocused();
  for(let i=0;i<8;i++){
    await page.keyboard.press('Tab');
    expect(await page.evaluate(()=>document.activeElement?.closest('dialog')?.classList.contains('agent-modal'))).toBeTruthy();
  }
  await page.keyboard.press('Escape');
  await expect(modal).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test('mobile AI modal fits the screen and respects reduced motion',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[product],total:1,version:'test',categories:['Skin Care']}}));
  await page.goto('/');
  await page.getByRole('button',{name:'Talk to Luma',exact:true}).click();
  const modal=page.getByRole('dialog',{name:'Talk to Luma'});
  await expect(modal).toBeVisible();
  const bounds=await modal.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(390);
  expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(844);
  expect(await modal.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBeTruthy();
  expect(await page.locator('.mobile-agent-avatar .orb-halo').evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
  await expect(page.getByRole('button',{name:'Send message',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Close beauty guide'}).click();
  await expect(modal).not.toBeVisible();
});

test('chat quota rejection is visible and re-enables input',async({page})=>{
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[product],total:1,version:'test',categories:['Skin Care']}}));
  await page.route('**/api/chat',route=>route.fulfill({status:429,json:{detail:'The demo chat allowance has been reached'}}));
  await page.goto('/');
  await expect(page.getByRole('button',{name:`View ${product.title}`,exact:true})).toBeVisible();
  await page.locator('.chat-launcher').click();
  await page.getByLabel('Message your beauty guide').fill('Hello');
  await page.getByRole('button',{name:'Send message'}).click();
  await expect(page.getByRole('alert')).toHaveText('The demo chat allowance has been reached');
  await expect(page.getByLabel('Message your beauty guide')).toBeEnabled();
});

test('Enter sends a message and avatar changes while the AI is thinking',async({page})=>{
  let complete!:()=>void;
  const gate=new Promise<void>(resolve=>{complete=resolve;});
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[product],total:1,version:'test',categories:['Skin Care']}}));
  await page.route('**/api/chat',async route=>{
    await gate;
    await route.fulfill({contentType:'text/event-stream',body:'event: answer\ndata: {"text":"A test-only answer."}\n\nevent: recommendations\ndata: {"products":[]}\n\nevent: done\ndata: {"turns_remaining":9}\n\n'});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Talk to Luma',exact:true}).click();
  const input=page.getByLabel('Message your beauty guide');
  await expect(input).toBeEnabled();
  await input.fill('Find a moisturizer');
  await input.press('Enter');
  await expect(page.getByText('Thinking through your request')).toBeVisible();
  await expect(page.locator('.modal-orb-stage .agent-orb')).toHaveClass(/is-thinking/);
  await expect(input).toBeDisabled();
  complete();
  await expect(page.getByText('A test-only answer.')).toBeVisible();
  await expect(page.getByText('Ready when you are')).toBeVisible();
  await expect(input).toBeFocused();
});

test('modal shrinks back toward its launcher and can be reopened',async({page})=>{
  await page.setViewportSize({width:1440,height:1000});
  await page.route('**/api/products?*',route=>route.fulfill({json:{products:[product],total:1,version:'test',categories:['Skin Care']}}));
  await page.goto('/');
  const launcher=page.locator('.chat-launcher');
  const source=(await launcher.boundingBox())!;
  await launcher.click();
  const modal=page.locator('.agent-modal');
  await expect(modal).toHaveAttribute('data-phase','open');
  await page.getByRole('button',{name:'Close beauty guide'}).click();
  await expect(modal).toHaveAttribute('data-phase','closing');
  await modal.evaluate(el=>{
    const motion=el.getAnimations().find(a=>(a.effect as KeyframeEffect)?.target===el)!;
    motion.pause();
    motion.currentTime=Number(motion.effect!.getTiming().duration)*.99;
  });
  const shrinking=(await modal.boundingBox())!;
  expect(shrinking.width).toBeLessThan(300);
  expect(Math.abs(shrinking.x+shrinking.width/2-(source.x+source.width/2))).toBeLessThan(100);
  expect(Math.abs(shrinking.y+shrinking.height/2-(source.y+source.height/2))).toBeLessThan(100);
  await modal.evaluate(el=>el.getAnimations().find(a=>(a.effect as KeyframeEffect)?.target===el)!.finish());
  await expect(modal).not.toBeVisible();
  await expect(launcher).toBeFocused();
  await launcher.click();
  await expect(modal).toHaveAttribute('data-phase','open');
});
