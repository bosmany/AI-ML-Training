import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payments import PaymentService, Processor  # noqa: E402


@pytest.fixture
def svc(tmp_path):
    return PaymentService(str(tmp_path / "pay.db"), Processor(latency=0))
