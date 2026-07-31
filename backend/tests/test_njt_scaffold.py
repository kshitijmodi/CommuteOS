import pytest

from app.transit.njt import NjtCredentials, get_arrivals


@pytest.mark.asyncio
async def test_get_arrivals_raises_not_implemented():
    """Regression guard: this must keep failing loudly, not silently
    return empty/fake data, until real credentials/format are confirmed.
    """
    with pytest.raises(NotImplementedError):
        await get_arrivals("NY", NjtCredentials(username="x", password="y"))
