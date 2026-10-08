"""M4: Moku ADC LSB and quantization noise (SPEC §4.7)."""

import math
from typing import Any

import numpy as np
import pytest

from srsfe.core.moku import lsb, quantization_noise
from tests import golden


@pytest.mark.golden
@pytest.mark.spec("§9.1", "lsb", "v_q")
@pytest.mark.spec("§4.7", "lsb")
def test_golden_lsb(golden_params: dict[str, Any]) -> None:
    """1 V range, 12 bits: LSB and V_q match SPEC §9.1."""
    q = lsb(golden_params["v_range"], golden_params["n_bits"])
    assert q == pytest.approx(golden.LSB, rel=golden.REL)
    assert quantization_noise(q) == pytest.approx(golden.V_Q, rel=golden.REL)


@pytest.mark.formula
@pytest.mark.spec("§4.7", "lsb")
def test_lsb_scaling() -> None:
    """LSB scales with range and halves per extra bit."""
    assert lsb(10.0, 12) == pytest.approx(10 * lsb(1.0, 12), rel=1e-12)
    assert lsb(1.0, 13) == pytest.approx(lsb(1.0, 12) / 2, rel=1e-12)


@pytest.mark.formula
@pytest.mark.spec("§4.7", "lsb")
def test_v_q_is_rms_of_uniform_error() -> None:
    """LSB/√12 equals the rms of an error spread uniformly over one LSB (numerical check)."""
    q = lsb(1.0, 12)
    err = np.linspace(-q / 2, q / 2, 1_000_001)
    assert quantization_noise(q) == pytest.approx(float(np.sqrt(np.mean(err**2))), rel=1e-5)
    assert quantization_noise(q) == pytest.approx(q / math.sqrt(12), rel=1e-12)


@pytest.mark.validation
@pytest.mark.parametrize(
    ("func", "args"),
    [(lsb, (0, 12)), (lsb, (1.0, 0)), (lsb, (1.0, 12.0)), (lsb, (1.0, True)),
     (quantization_noise, (0,)), (quantization_noise, (float("inf"),))],
)
def test_rejects_bad_input(func: Any, args: tuple[Any, ...]) -> None:
    """Non-positive range, non-integer or < 1 bits and non-positive LSB raise ValueError."""
    with pytest.raises(ValueError):
        func(*args)
