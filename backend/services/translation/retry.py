from __future__ import annotations

import time
from typing import Callable


class AdaptivePacer:
    """Адаптивная пауза между AI-запросами вместо фиксированного sleep(6).

    Пауза растёт (x2) после ошибок квоты и плавно снижается (/2) после
    успешных запросов, поэтому сервис сам подстраивается под лимит
    текущего тарифа, не тормозя без необходимости.

    Сами ретраи 429 делает провайдер (он знает retryDelay); этот класс
    отвечает только за интервал между запросами.
    """

    def __init__(
        self,
        initial_delay: float = 2.0,
        min_delay: float = 1.0,
        max_delay: float = 30.0,
        factor: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._delay = initial_delay
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._factor = factor
        self._sleep = sleep

    @property
    def delay(self) -> float:
        return self._delay

    def wait(self) -> None:
        if self._delay > 0:
            self._sleep(self._delay)

    def on_success(self) -> None:
        self._delay = max(self._min_delay, self._delay / self._factor)

    def on_rate_limit(self) -> None:
        self._delay = min(self._max_delay, self._delay * self._factor)
