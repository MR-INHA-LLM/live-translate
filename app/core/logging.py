"""로깅 설정 (python-standards §10 — print 금지, logging 모듈 사용)."""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    """루트 로거를 표준 포맷으로 구성한다.

    Args:
        level: 로그 레벨 문자열(예: "INFO", "DEBUG").
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
