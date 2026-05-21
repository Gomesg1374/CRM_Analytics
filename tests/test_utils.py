"""
Unit tests for etl/utils.py — normalizar_texto() and adicionar_vendedor_loja().
Run with: pytest tests/test_utils.py -v
"""
import numpy as np
import pandas as pd
import pytest

from etl.utils import normalizar_texto, adicionar_vendedor_loja


# ============================================================
# normalizar_texto
# ============================================================

class TestNormalizarTexto:
    def test_remove_accents(self):
        s = pd.Series(["Cão", "João", "Ação"])
        assert normalizar_texto(s).tolist() == ["cao", "joao", "acao"]

    def test_lowercase(self):
        assert normalizar_texto(pd.Series(["ABC", "DeF"])).tolist() == ["abc", "def"]

    def test_strip_leading_trailing_whitespace(self):
        assert normalizar_texto(pd.Series(["  abc  ", "xyz "])).tolist() == ["abc", "xyz"]

    def test_collapse_internal_spaces(self):
        assert normalizar_texto(pd.Series(["a  b", "c   d"])).tolist() == ["a b", "c d"]

    def test_remove_special_characters(self):
        result = normalizar_texto(pd.Series(["a.b", "c-d", "e@f"]))
        assert result.tolist() == ["ab", "cd", "ef"]

    def test_nan_and_none_become_empty_string(self):
        result = normalizar_texto(pd.Series([np.nan, None, "ok"]))
        assert result[0] == ""
        assert result[1] == ""
        assert result[2] == "ok"

    def test_numeric_characters_preserved(self):
        assert normalizar_texto(pd.Series(["lead123"])).tolist() == ["lead123"]

    def test_mixed_case_with_accents_and_spaces(self):
        assert normalizar_texto(pd.Series(["  João  da  Silva  "])).tolist() == ["joao da silva"]


# ============================================================
# adicionar_vendedor_loja
# ============================================================

@pytest.fixture
def dim_vendedores():
    return pd.DataFrame([
        {"id_vendedor": 1, "nome": "joao"},
        {"id_vendedor": 2, "nome": "maria"},
    ])


@pytest.fixture
def hist():
    return pd.DataFrame([
        # João: Loja A in 2022, Loja B from 2023 onward
        {"id_vendedor": 1, "id_loja": 10, "loja": "Loja A",
         "data_inicio": pd.Timestamp("2022-01-01"), "data_fim": pd.Timestamp("2022-12-31")},
        {"id_vendedor": 1, "id_loja": 20, "loja": "Loja B",
         "data_inicio": pd.Timestamp("2023-01-01"), "data_fim": pd.NaT},
        # Maria: Loja A always
        {"id_vendedor": 2, "id_loja": 10, "loja": "Loja A",
         "data_inicio": pd.Timestamp("2022-01-01"), "data_fim": pd.NaT},
    ])


@pytest.fixture
def de_para_vend():
    return pd.DataFrame([
        {"nome_origem": "j silva", "nome_padrao": "joao"},
    ])


class TestAdicionarVendedorLoja:
    def test_no_rows_dropped_for_known_vendor(self, dim_vendedores, hist, de_para_vend):
        """R2: rows must never be dropped."""
        df = pd.DataFrame([
            {"resp": "joao",  "data": pd.Timestamp("2022-06-01")},
            {"resp": "maria", "data": pd.Timestamp("2022-06-01")},
        ])
        result = adicionar_vendedor_loja(df, "resp", "data", dim_vendedores, hist, de_para_vend)
        assert len(result) == len(df)

    def test_no_rows_dropped_for_unknown_vendor(self, dim_vendedores, hist, de_para_vend):
        """R2: unknown vendor must not drop the row."""
        df = pd.DataFrame([
            {"resp": "desconhecido_xyz", "data": pd.Timestamp("2022-06-01")},
        ])
        result = adicionar_vendedor_loja(df, "resp", "data", dim_vendedores, hist, de_para_vend)
        assert len(result) == 1

    def test_unknown_vendor_gets_id_minus_one(self, dim_vendedores, hist, de_para_vend):
        """R2: id_vendedor = -1 for unmatched sellers."""
        df = pd.DataFrame([{"resp": "ninguem", "data": pd.Timestamp("2022-06-01")}])
        result = adicionar_vendedor_loja(df, "resp", "data", dim_vendedores, hist, de_para_vend)
        assert result["id_vendedor"].iloc[0] == -1
        assert result["id_loja"].iloc[0] == -1

    def test_historical_loja_resolution(self, dim_vendedores, hist, de_para_vend):
        """R1: loja resolves to the store the vendor worked at ON the event date."""
        df = pd.DataFrame([
            {"resp": "joao", "data": pd.Timestamp("2022-06-01")},   # → Loja A (id 10)
            {"resp": "joao", "data": pd.Timestamp("2023-06-01")},   # → Loja B (id 20)
        ])
        result = adicionar_vendedor_loja(df, "resp", "data", dim_vendedores, hist, de_para_vend)
        assert result.iloc[0]["id_loja"] == 10, "2022 event should resolve to Loja A"
        assert result.iloc[1]["id_loja"] == 20, "2023 event should resolve to Loja B"

    def test_de_para_vendor_mapping(self, dim_vendedores, hist, de_para_vend):
        """R3: de/para is applied before the vendor lookup."""
        df = pd.DataFrame([{"resp": "j silva", "data": pd.Timestamp("2023-06-01")}])
        result = adicionar_vendedor_loja(df, "resp", "data", dim_vendedores, hist, de_para_vend)
        assert result["id_vendedor"].iloc[0] == 1, "'j silva' should map to joao (id=1) via de/para"

    def test_multiple_rows_same_vendor(self, dim_vendedores, hist, de_para_vend):
        """Multiple events for the same vendor are all resolved independently."""
        df = pd.DataFrame([
            {"resp": "joao", "data": pd.Timestamp("2022-03-01")},
            {"resp": "joao", "data": pd.Timestamp("2022-09-01")},
            {"resp": "joao", "data": pd.Timestamp("2023-03-01")},
        ])
        result = adicionar_vendedor_loja(df, "resp", "data", dim_vendedores, hist, de_para_vend)
        assert len(result) == 3
        assert result.iloc[0]["id_loja"] == 10
        assert result.iloc[1]["id_loja"] == 10
        assert result.iloc[2]["id_loja"] == 20

    def test_id_columns_are_integers(self, dim_vendedores, hist, de_para_vend):
        """id_vendedor and id_loja must be integer dtype (not float)."""
        df = pd.DataFrame([
            {"resp": "joao",    "data": pd.Timestamp("2022-06-01")},
            {"resp": "ninguem", "data": pd.Timestamp("2022-06-01")},
        ])
        result = adicionar_vendedor_loja(df, "resp", "data", dim_vendedores, hist, de_para_vend)
        assert result["id_vendedor"].dtype in (int, "int64", "int32")
        assert result["id_loja"].dtype in (int, "int64", "int32")
