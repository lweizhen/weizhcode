"""只估算实际准备发送的请求；不把缓存token重复加到input上。"""
from dataclasses import dataclass
import math


def chars_tokens(text):
    return math.ceil(len(text) / 3.5)


def projected_tokens(request):
    return chars_tokens(request.fixed_projection + ''.join(request.message_projections))


def projected_chars(request):
    return len(request.fixed_projection) + sum(map(len, request.message_projections))


@dataclass(frozen=True)
class UsageAnchor:
    fixed_digest: str
    projections: tuple[str, ...]
    tokens: int
    projected_chars: int


class TokenEstimator:
    def __init__(self, runtime):
        self.runtime = runtime

    def estimate(self, request, *, invalidate=True):
        anchor = self.runtime.anchor
        # 动态提醒仍计入实际body体积，但不被误当历史尾项参与前缀匹配。
        # 内容改变仍由fixed_digest失效；增量按完整实际投影差额计算，不重加提醒。
        parts = request.anchor_projections
        if (anchor is not None and anchor.fixed_digest == request.fixed_digest
                and parts[:len(anchor.projections)] == anchor.projections
                and projected_chars(request) >= anchor.projected_chars):
            return anchor.tokens + math.ceil((projected_chars(request)-anchor.projected_chars)/3.5)
        if invalidate:
            self.runtime.anchor = None
        return projected_tokens(request)

    def observe(self, request_with_response, usage, *, completed):
        if request_with_response.purpose != 'chat':
            return False
        if (completed and usage.complete
                and usage.input_tokens is not None and usage.output_tokens is not None):
            self.runtime.anchor = UsageAnchor(request_with_response.fixed_digest,
                request_with_response.anchor_projections, usage.input_tokens + usage.output_tokens,
                projected_chars(request_with_response))
            return True
        self.runtime.anchor = None
        return False

    def fits(self, request, *, invalidate=True):
        return self.estimate(request, invalidate=invalidate) + request.output_reserve + 3000 <= self.runtime.context_window
