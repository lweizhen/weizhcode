from .archive import SessionStore
from .capture import CaptureHub
from .state import SessionRuntime


def build_context_runtime(*, root_identity, context_window, redactor, store_factory=SessionStore):
    runtime = SessionRuntime(context_window=context_window, root=root_identity)
    runtime.store = store_factory(root_identity, runtime.session_id, redactor)
    runtime.sources = CaptureHub(redactor, is_current=runtime.is_current)
    return runtime


class NoopContextManager:
    """仅供显式注入的旧测试/独立嵌入，不是生产默认。"""
    runtime = None

    async def aclose(self):
        pass
