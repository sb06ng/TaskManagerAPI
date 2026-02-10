from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def ensure_utc(v: datetime | None) -> datetime | None:
    """
    Ensures a datetime object is timezone-aware (UTC).
    Does NOT check if the date is in the future.
    Use this for creation_date and completion_date.
    """
    if v is None:
        return v
    if isinstance(v, str):
        v = datetime.fromisoformat(v)
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    else:
        v = v.astimezone(timezone.utc)
    return v


def date_utc_validator_factory(
    get_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Callable[[datetime | None], datetime | None]:
    """
    Creates a validator function.
    By default, it uses the real 'now', but you can override it in tests.
    """

    def validate(v: datetime | None) -> datetime | None:
        """Reusable logic for date normalization and future-check."""
        v = ensure_utc(v)
        if v is None:
            return v

        now = get_now()
        if v < now:
            raise ValueError(
                f"Date must be in the future. Provided: {v}, Current: {now}"
            )
        return v

    return validate
