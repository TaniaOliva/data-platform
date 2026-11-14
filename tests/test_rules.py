"""Pruebas de las reglas de calidad y utilidades del ETL (D-18, D-19)."""
from datetime import date, datetime

from etl.extract.extract_raw import type_ddl
from etl.load.load_dw import date_rows
from etl.sqlutil import build_merge
from etl.transform import rules
from etl.transform.rules import Violation

CTX = {"invoice_is_credit_note": {1: False, 2: True}}


def line(**kw):
    base = {"_key": "10", "InvoiceLineID": 10, "InvoiceID": 1, "StockItemID": 5, "Quantity": 3,
            "TaxRate": 15, "TaxAmount": 1, "LineProfit": 1, "ExtendedPrice": 1}
    base.update(kw)
    return base


# --- R01 valores obligatorios
def test_required_value_passes_when_all_present():
    assert rules.required_value(("a", "b"))({"a": 1, "b": 0}, {}) is None


def test_required_value_zero_is_not_null():
    # D-19: cero es un valor real, solo None cuenta como faltante
    assert rules.required_value(("a",))({"a": 0}, {}) is None


def test_required_value_reports_missing_columns():
    detail = rules.required_value(("a", "b", "c"))({"a": 1, "b": None, "c": None}, {})
    assert "b" in detail and "c" in detail and "a" not in detail.replace("Columnas nulas", "")


# --- R02 cantidad negativa
def test_negative_qty_in_regular_invoice_fails():
    assert rules.negative_qty_not_credit_note(line(Quantity=-2, InvoiceID=1), CTX) is not None


def test_negative_qty_in_credit_note_passes():
    assert rules.negative_qty_not_credit_note(line(Quantity=-2, InvoiceID=2), CTX) is None


def test_positive_qty_passes():
    assert rules.negative_qty_not_credit_note(line(Quantity=4), CTX) is None


# --- R03 línea huérfana
def test_orphan_line_detected():
    assert rules.orphan_invoice_line(line(InvoiceID=99), CTX) is not None


def test_line_with_invoice_is_not_orphan():
    assert rules.orphan_invoice_line(line(InvoiceID=1), CTX) is None


# --- R04 rango de fechas
def test_date_in_range_accepts_boundaries():
    rule = rules.date_in_range("InvoiceDate")
    assert rule({"InvoiceDate": date(2013, 1, 1)}, {}) is None
    assert rule({"InvoiceDate": date(2016, 12, 31)}, {}) is None


def test_date_out_of_range_fails():
    rule = rules.date_in_range("InvoiceDate")
    assert rule({"InvoiceDate": date(2012, 12, 31)}, {}) is not None
    assert rule({"InvoiceDate": datetime(2017, 1, 1, 8)}, {}) is not None


# --- R05 vigencia
def test_valid_range():
    assert rules.valid_range({"ValidFrom": datetime(2013, 1, 1), "ValidTo": datetime(2014, 1, 1)}, {}) is None
    assert rules.valid_range({"ValidFrom": datetime(2014, 1, 1), "ValidTo": datetime(2014, 1, 1)}, {}) is not None


# --- evaluate
def test_evaluate_returns_one_violation_per_failed_rule():
    out = rules.evaluate("Sales.InvoiceLines", [line(InvoiceID=99, Quantity=-1)], CTX)
    assert {v.rule_id for v in out} == {rules.R03_ORPHAN_LINE}  # R02 no aplica sin factura
    assert isinstance(out[0], Violation) and out[0].key == "10"


def test_evaluate_clean_rows_produce_nothing():
    assert rules.evaluate("Sales.InvoiceLines", [line()], CTX) == []


def test_every_source_rule_has_description():
    ids = {rid for lst in rules.RULES_BY_SOURCE.values() for rid, _ in lst}
    assert ids <= set(rules.RULE_DESCRIPTIONS)


# --- utilidades
def test_type_ddl_keeps_precision_and_length():
    assert type_ddl("decimal", 9, 18, 3) == "decimal(18,3)"
    assert type_ddl("nvarchar", 100, 0, 0) == "nvarchar(50)"
    assert type_ddl("nvarchar", -1, 0, 0) == "nvarchar(max)"
    assert type_ddl("datetime2", 8, 27, 7) == "datetime2(7)"


def test_build_merge_is_idempotent_by_design():
    sql = build_merge("t.X", "SELECT 1 AS Id, 2 AS V", ["Id"], ["Id", "V"])
    assert "INTERSECT" in sql  # solo actualiza si cambió algo
    assert "WHEN NOT MATCHED BY TARGET" in sql and "ON t.[Id] = s.[Id]" in sql


def test_date_dimension_covers_2013_to_2016():
    rows = list(date_rows())
    assert rows[0][0] == 20130101 and rows[-1][0] == 20161231
    assert len(rows) == 1461  # 4 años, 2016 bisiesto
    assert len({r[0] for r in rows}) == len(rows)
    saturday = next(r for r in rows if r[0] == 20130105)
    assert saturday[7] == 1 and saturday[4] == "enero" and saturday[5] == 1
