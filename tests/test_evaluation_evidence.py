import asyncio
import json
from types import SimpleNamespace
from beauty.catalog import Catalog
from scripts import evaluate_hardening
from agent.app import agent


def test_grader_receives_retrieved_evidence_without_recommendation_cards(monkeypatch, tmp_path, product):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'evals').mkdir()
    (tmp_path/'reports').mkdir()
    (tmp_path/'agent/app').mkdir(parents=True)
    (tmp_path/'agent/app/agent.py').write_text('synthetic tested source')
    (tmp_path/'agent/app/shopping.py').write_text('synthetic tested runner')
    (tmp_path/'evals/hardening.json').write_text(json.dumps([
        {'id':'ingredients','mode':'model','messages':['Are ingredients listed?']}]))
    monkeypatch.setattr(evaluate_hardening,'get_catalog',lambda:Catalog([product]))
    monkeypatch.setattr(evaluate_hardening.logger,'disabled',False)
    original = agent.evidence
    async def response(payload):
        agent.evidence(product)  # Actual tool evidence; no recommendation card.
        yield {'type':'result','answer':'The catalog has limited ingredient information.',
            'product_ids':[],'usage':{'input_tokens':0,'output_tokens':0}}
    monkeypatch.setattr(evaluate_hardening,'respond',response)
    asyncio.run(evaluate_hardening.run(SimpleNamespace(live=True,output=None,runtime_resource='synthetic')))
    result = json.loads((tmp_path/'reports/hardening-evaluation.json').read_text())['cases'][0]
    assert result['product_ids'] == []
    assert json.loads(result['context'])[0]['id'] == product.id
    assert result['evidence_source'] == 'actual_tool_and_prior_product_evidence'
    assert agent.evidence is original
