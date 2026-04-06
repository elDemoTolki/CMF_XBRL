"""
Tests for ratios.py module.
"""

import pytest
import pandas as pd
import numpy as np

from ratios import RatioSpec, _compute_spec, _val, compute_ratios, RATIOS


class TestRatioSpec:
    """Tests for RatioSpec dataclass."""
    
    def test_create_ratio_spec(self):
        """Test creating a ratio specification."""
        spec = RatioSpec(
            name="roe",
            label="ROE",
            numerator="net_income",
            denominator="equity",
            category="profitability",
            pct=True
        )
        assert spec.name == "roe"
        assert spec.negate_num == False
        assert spec.for_banks == False
        assert spec.not_for_banks == False
    
    def test_ratios_list_not_empty(self):
        """Test that RATIOS list is populated."""
        assert len(RATIOS) > 0
        # Check essential ratios exist
        ratio_names = [r.name for r in RATIOS]
        assert "roe" in ratio_names
        assert "roa" in ratio_names
        assert "debt_to_equity" in ratio_names


class TestValFunction:
    """Tests for _val helper function."""
    
    def test_val_from_dict(self):
        """Test extracting value from dictionary."""
        row = {"net_income": 100.0, "equity": 500.0}
        assert _val(row, "net_income") == 100.0
        assert _val(row, "equity") == 500.0
    
    def test_val_missing_key(self):
        """Test extracting missing key returns None."""
        row = {"net_income": 100.0}
        assert _val(row, "equity") is None
    
    def test_val_nan_returns_none(self):
        """Test that NaN values return None."""
        row = {"net_income": float('nan')}
        assert _val(row, "net_income") is None
    
    def test_val_none_returns_none(self):
        """Test that None values return None."""
        row = {"net_income": None}
        assert _val(row, "net_income") is None
    
    def test_val_from_namedtuple(self):
        """Test extracting value from namedtuple (itertuples result)."""
        from collections import namedtuple
        Row = namedtuple('Row', ['net_income', 'equity'])
        row = Row(net_income=100.0, equity=500.0)
        assert _val(row, "net_income") == 100.0
        assert _val(row, "equity") == 500.0


class TestComputeSpec:
    """Tests for _compute_spec function."""
    
    def test_compute_basic_ratio(self):
        """Test basic ratio computation."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": 100.0, "equity": 500.0}
        
        ratio, quality, num, den, abs_den = _compute_spec(row, spec)
        
        assert ratio == pytest.approx(0.2, rel=1e-3)
        assert quality == "reliable"
        assert num == 100.0
        assert den == 500.0
        assert abs_den == 500.0
    
    def test_compute_missing_numerator(self):
        """Test ratio with missing numerator."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": None, "equity": 500.0}
        
        ratio, quality, _, _, _ = _compute_spec(row, spec)
        
        assert ratio is None
        assert quality == "missing_numerator"
    
    def test_compute_missing_denominator(self):
        """Test ratio with missing denominator."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": 100.0, "equity": None}
        
        ratio, quality, _, _, _ = _compute_spec(row, spec)
        
        assert ratio is None
        assert quality == "missing_denominator"
    
    def test_compute_zero_denominator(self):
        """Test ratio with zero denominator."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": 100.0, "equity": 0.0}
        
        ratio, quality, _, _, _ = _compute_spec(row, spec)
        
        assert ratio is None
        assert quality == "zero_denominator"
    
    def test_compute_negative_denominator(self):
        """Test ratio with negative denominator (uses absolute value)."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": 100.0, "equity": -500.0}
        
        ratio, quality, _, den, abs_den = _compute_spec(row, spec)
        
        assert ratio == pytest.approx(0.2, rel=1e-3)
        assert abs_den == 500.0
    
    def test_compute_negate_numerator(self):
        """Test ratio with negated numerator."""
        spec = RatioSpec("test", "Test", "expense", "revenue", "test", negate_num=True)
        row = {"expense": 100.0, "revenue": 500.0}
        
        ratio, _, _, _, _ = _compute_spec(row, spec)
        
        # -100 / 500 = -0.2
        assert ratio == pytest.approx(-0.2, rel=1e-3)


class TestComputeRatios:
    """Tests for compute_ratios function."""
    
    def test_compute_ratios_basic(self):
        """Test computing ratios on a DataFrame."""
        df = pd.DataFrame([
            {
                "ticker": "TEST.SN",
                "year": 2023,
                "month": 12,
                "industry": "non_financial",
                "net_income": 100.0,
                "equity": 500.0,
                "assets": 1000.0,
                "revenue": 2000.0,
                "ebit": 200.0,
                "debt_total": 300.0,
                "current_assets": 400.0,
                "current_liabilities": 200.0,
            }
        ])
        
        result = compute_ratios(df)
        
        assert len(result) == 1
        assert "roe" in result.columns
        assert "roa" in result.columns
        assert "debt_to_equity" in result.columns
        assert result["roe"].iloc[0] == pytest.approx(0.2, rel=1e-3)
        assert result["roa"].iloc[0] == pytest.approx(0.1, rel=1e-3)
    
    def test_compute_ratios_bank_excludes_debt_ratios(self):
        """Test that bank rows don't get debt ratios."""
        df = pd.DataFrame([
            {
                "ticker": "BANK.SN",
                "year": 2023,
                "month": 12,
                "industry": "financial",
                "net_income": 100.0,
                "equity": 500.0,
                "assets": 1000.0,
                "debt_total": 300.0,  # Should be ignored
            }
        ])
        
        result = compute_ratios(df)
        
        assert result["debt_to_equity"].iloc[0] is None
        assert result["debt_to_equity_quality"].iloc[0] == "not_applicable"
    
    def test_compute_ratios_non_bank_excludes_bank_ratios(self):
        """Test that non-bank rows don't get bank-specific ratios."""
        df = pd.DataFrame([
            {
                "ticker": "TEST.SN",
                "year": 2023,
                "month": 12,
                "industry": "non_financial",
                "net_income": 100.0,
                "equity": 500.0,
                "loans_to_customers": 800.0,  # Should be ignored for bank ratios
            }
        ])
        
        result = compute_ratios(df)
        
        assert result["nim"].iloc[0] is None
        assert result["nim_quality"].iloc[0] == "not_applicable"
    
    def test_compute_ratios_quality_columns(self):
        """Test that quality columns are created."""
        df = pd.DataFrame([
            {
                "ticker": "TEST.SN",
                "year": 2023,
                "month": 12,
                "industry": "non_financial",
                "net_income": 100.0,
                "equity": 500.0,
            }
        ])
        
        result = compute_ratios(df)
        
        assert "roe_quality" in result.columns
        assert result["roe_quality"].iloc[0] == "reliable"


class TestRatioEdgeCases:
    """Tests for edge cases in ratio computation."""
    
    def test_very_large_values(self):
        """Test ratio computation with very large values."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": 1e15, "equity": 5e15}
        
        ratio, _, _, _, _ = _compute_spec(row, spec)
        assert ratio == pytest.approx(0.2, rel=1e-6)
    
    def test_very_small_values(self):
        """Test ratio computation with very small values."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": 1e-10, "equity": 5e-10}
        
        ratio, _, _, _, _ = _compute_spec(row, spec)
        assert ratio == pytest.approx(0.2, rel=1e-6)
    
    def test_negative_numerator(self):
        """Test ratio with negative numerator (loss)."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": -100.0, "equity": 500.0}
        
        ratio, _, _, _, _ = _compute_spec(row, spec)
        assert ratio == pytest.approx(-0.2, rel=1e-3)
    
    def test_both_negative(self):
        """Test ratio with both values negative."""
        spec = RatioSpec("roe", "ROE", "net_income", "equity", "profitability")
        row = {"net_income": -100.0, "equity": -500.0}
        
        ratio, _, _, _, _ = _compute_spec(row, spec)
        # -100 / |-500| = -0.2
        assert ratio == pytest.approx(-0.2, rel=1e-3)