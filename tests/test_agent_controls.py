from types import SimpleNamespace
import pytest
from agent.app import agent
from beauty.catalog import Catalog


@pytest.mark.asyncio
async def test_tool_allowances_and_grounded_ids(monkeypatch,product):
    monkeypatch.setattr(agent,'get_catalog',lambda:Catalog([product]))
    context=SimpleNamespace(state={})
    result=await agent.search_products('moisturizer',context,max_price_usd=9)
    assert result['products']==[] and context.state['allowed_product_ids']==[]
    result=await agent.search_products('moisturizer',context,max_price_usd=10)
    assert result['products'][0]['id']==product.id
    assert context.state['allowed_product_ids']==[product.id]
    assert agent.get_product('not-a-product',context)=={'error':'Product not found'}
    agent.get_product(product.id,context)
    with pytest.raises(RuntimeError,match='Tool allowance'):
        agent.get_product(product.id,context)


@pytest.mark.asyncio
async def test_token_allowance_fails_closed(monkeypatch):
    class AsyncClient:
        def __init__(self):self.models=self
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def count_tokens(self,**kwargs):return SimpleNamespace(total_tokens=6000)
    owner=SimpleNamespace(aio=AsyncClient())
    monkeypatch.setattr(agent,'model_client',lambda:owner)
    context=SimpleNamespace(state={})
    request=SimpleNamespace(contents=[],config=SimpleNamespace(system_instruction=None,tools=None))
    await agent.input_budget(context,request)
    assert context.state['input_budget_used']==7024
    assert request.config.tool_config.function_calling_config.mode == 'ANY'
    assert request.config.tool_config.function_calling_config.allowed_function_names == ['search_products']
    with pytest.raises(RuntimeError,match='token allowance'):
        await agent.input_budget(context,request)


def test_usage_includes_reasoning():
    context=SimpleNamespace(state={})
    response=SimpleNamespace(usage_metadata=SimpleNamespace(prompt_token_count=100,candidates_token_count=20,thoughts_token_count=5))
    agent.record_usage(context,response)
    agent.record_usage(context,response)
    assert context.state['usage']=={'input_tokens':200,'output_tokens':50}
