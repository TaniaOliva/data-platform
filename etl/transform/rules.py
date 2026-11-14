"""Reglas de calidad (D-18, D-19, D-20) como funciones puras.

Cada regla recibe una fila (dict) y un contexto, y devuelve None si la fila cumple
o un texto con el detalle si la incumple. Los incumplimientos van a stg.Quarantine.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Optional

# Rango cubierto por dim.DimDate
DATE_MIN = date(2013, 1, 1)
DATE_MAX = date(2016, 12, 31)

# Identificadores del catálogo de reglas
R01_REQUIRED = "R01_REQUIRED_VALUE"
R02_NEGATIVE_QTY = "R02_NEGATIVE_QTY_NOT_CREDIT_NOTE"
R03_ORPHAN_LINE = "R03_ORPHAN_INVOICE_LINE"
R04_DATE_RANGE = "R04_DATE_OUT_OF_RANGE"
R05_VALIDITY = "R05_INVALID_VALIDITY_RANGE"

RULE_DESCRIPTIONS = {
    R01_REQUIRED: "Las columnas obligatorias (llaves, fechas y medidas) no pueden ser nulas.",
    R02_NEGATIVE_QTY: "Una cantidad negativa solo es válida en una nota de crédito.",
    R03_ORPHAN_LINE: "Toda línea de factura debe pertenecer a una factura existente.",
    R04_DATE_RANGE: "La fecha de factura debe estar dentro del rango de dim.DimDate (2013 a 2016).",
    R05_VALIDITY: "ValidFrom debe ser anterior a ValidTo.",
}


@dataclass(frozen=True)
class Violation:
    key: str
    rule_id: str
    detail: str


Row = dict
Rule = Callable[[Row, dict], Optional[str]]


def required_value(columns: tuple[str, ...]) -> Rule:
    """R01: ninguna de las columnas indicadas puede ser nula."""
    def rule(row: Row, ctx: dict) -> Optional[str]:
        missing = [c for c in columns if row.get(c) is None]
        return f"Columnas nulas: {', '.join(missing)}" if missing else None
    return rule


def negative_qty_not_credit_note(row: Row, ctx: dict) -> Optional[str]:
    """R02: cantidad negativa en una factura que no es nota de crédito."""
    qty = row.get("Quantity")
    if qty is None or qty >= 0:
        return None
    is_credit = ctx.get("invoice_is_credit_note", {}).get(row.get("InvoiceID"))
    if is_credit is None:
        return None  # sin factura: lo reporta R03
    if not is_credit:
        return f"Quantity={qty} en la factura {row.get('InvoiceID')}, que no es nota de crédito"
    return None


def orphan_invoice_line(row: Row, ctx: dict) -> Optional[str]:
    """R03: la factura de la línea no existe."""
    invoices = ctx.get("invoice_is_credit_note", {})
    if row.get("InvoiceID") is not None and row["InvoiceID"] not in invoices:
        return f"La factura {row['InvoiceID']} no existe"
    return None


def date_in_range(column: str) -> Rule:
    """R04: la fecha debe estar entre DATE_MIN y DATE_MAX."""
    def rule(row: Row, ctx: dict) -> Optional[str]:
        value = row.get(column)
        if value is None:
            return None  # lo reporta R01
        d = value.date() if isinstance(value, datetime) else value
        if not (DATE_MIN <= d <= DATE_MAX):
            return f"{column}={d.isoformat()} fuera de {DATE_MIN.isoformat()} a {DATE_MAX.isoformat()}"
        return None
    return rule


def valid_range(row: Row, ctx: dict) -> Optional[str]:
    """R05: ValidFrom debe ser menor que ValidTo."""
    start, end = row.get("ValidFrom"), row.get("ValidTo")
    if start is not None and end is not None and start >= end:
        return f"ValidFrom={start} no es anterior a ValidTo={end}"
    return None


# Reglas por fuente: (identificador, función)
RULES_BY_SOURCE: dict[str, list[tuple[str, Rule]]] = {
    "Application.People": [(R01_REQUIRED, required_value(("PersonID", "IsEmployee", "IsSalesperson")))],
    "Application.Countries": [(R01_REQUIRED, required_value(("CountryID",)))],
    "Application.StateProvinces": [(R01_REQUIRED, required_value(("StateProvinceID", "CountryID")))],
    "Application.Cities": [(R01_REQUIRED, required_value(("CityID", "StateProvinceID")))],
    "Sales.CustomerCategories": [(R01_REQUIRED, required_value(("CustomerCategoryID",)))],
    "Sales.Customers": [
        (R01_REQUIRED, required_value(("CustomerID", "ValidFrom", "ValidTo", "CustomerCategoryID", "DeliveryCityID"))),
        (R05_VALIDITY, valid_range),
    ],
    "Sales.Invoices": [
        (R01_REQUIRED, required_value(("InvoiceID", "CustomerID", "SalespersonPersonID", "InvoiceDate", "IsCreditNote"))),
        (R04_DATE_RANGE, date_in_range("InvoiceDate")),
    ],
    "Sales.InvoiceLines": [
        (R01_REQUIRED, required_value(("InvoiceLineID", "InvoiceID", "StockItemID", "Quantity",
                                       "TaxRate", "TaxAmount", "LineProfit", "ExtendedPrice"))),
        (R03_ORPHAN_LINE, orphan_invoice_line),
        (R02_NEGATIVE_QTY, negative_qty_not_credit_note),
    ],
    "Warehouse.StockGroups": [(R01_REQUIRED, required_value(("StockGroupID",)))],
    "Warehouse.StockItems": [(R01_REQUIRED, required_value(("StockItemID",)))],
    "Warehouse.StockItemStockGroups": [
        (R01_REQUIRED, required_value(("StockItemStockGroupID", "StockItemID", "StockGroupID")))
    ],
}


def evaluate(source: str, rows: list[Row], ctx: Optional[dict] = None, key_field: str = "_key") -> list[Violation]:
    """Aplica todas las reglas de la fuente; una fila puede incumplir varias."""
    ctx = ctx or {}
    out: list[Violation] = []
    for row in rows:
        for rule_id, rule in RULES_BY_SOURCE[source]:
            detail = rule(row, ctx)
            if detail:
                out.append(Violation(key=str(row[key_field]), rule_id=rule_id, detail=f"[{row[key_field]}] {detail}"))
    return out
