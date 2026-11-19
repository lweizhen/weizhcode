"""旧业务测试显式注入无压缩管理；上下文测试和生产装配测试保留真实路径。"""
import pytest


@pytest.fixture(autouse=True)
def legacy_context_injection(request, monkeypatch):
    path = request.node.path
    if path.name.startswith('test_context') or 'compact' in path.parts:
        return
    from weizhcode.turn_runner import TurnRunner
    from weizhcode.compact.factory import NoopContextManager
    original = TurnRunner.__init__
    def injected(self, *args, **kwargs):
        if 'context_runtime' not in kwargs and 'context_manager' not in kwargs:
            kwargs['context_manager'] = NoopContextManager()
        original(self, *args, **kwargs)
    monkeypatch.setattr(TurnRunner, '__init__', injected)
