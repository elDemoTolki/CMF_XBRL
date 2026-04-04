# CMF XBRL — Financial Data Pipeline

Pipeline completo para descargar, parsear y analizar estados financieros XBRL de empresas listadas en la Bolsa de Santiago, publicados por la CMF (Comisión para el Mercado Financiero).

> **Dos fuentes de datos:** empresas no-financieras y los bancos CHILE/BICE vienen del portal XBRL de CMF. Los bancos BCI, Santander e Itaú —que no publican XBRL— se poblan desde la **API SBIF v3** de CMF.

## Tabla de contenidos

1. [Arquitectura general](#arquitectura-general)
2. [Setup inicial](#setup-inicial)
3. [Universo de tickers](#universo-de-tickers)
4. [Descarga de archivos XBRL](#descarga-de-archivos-xbrl)
5. [Parseo XBRL → facts_raw](#parseo-xbrl--facts_raw)
6. [Warehouse financiero (no-financiero)](#warehouse-financiero)
7. [Datos bancarios — API CMF](#datos-bancarios--api-cmf)
8. [Ratios](#ratios)
9. [Consulta histórica por ticker](#consulta-histórica-por-ticker)
10. [Validación de datos](#validación-de-datos)
11. [Estructura de archivos](#estructura-de-archivos)
12. [Schema del warehouse](#schema-del-warehouse)
13. [Limitaciones conocidas](#limitaciones-conocidas)

---

## Arquitectura general

```
tickers_chile.json
      │
      ├─────────────────────────────────────────────────────────────┐
      ▼                                                             ▼
scraper/main.py                                            bank_pipeline.py
(empresas con XBRL)                                      (bancos sin XBRL)
      │                                                             │
      ▼                                                             │
xbrl_parser.py ──→ output/facts_raw.csv                            │
      │             (461k+ filas, todos los facts)                  │
      ▼                                                             │
pipeline.py ────→ output/warehouse.db ←─────────────────────────────┘
                  (normalized_financials, derived_metrics, quality_flags)
      │
      ▼
ratios.py ──────→ output/warehouse.db
                  (ratios, ratio_components, ratio_quality_flags)
      │
      ▼
query.py ───────→ consola / CSV / Excel           (historial de un ticker)
validate.py ────→ output/validation_report.xlsx   (comparación vs fuentes externas)
```


**Fuente de datos:** CMF RVEMI (empresas con valores de oferta pública bajo norma IFRS).  
**Período disponible:** 2010–presente (2010–2011 solo algunos tickers; cobertura completa desde 2012).  
**Moneda:** Cada empresa reporta en su moneda funcional (CLP o USD). El campo `reporting_currency` indica cuál usar.

---

## Setup inicial

### Requisitos

- Python 3.11+
- Git

### Instalación

```bash
git clone <repo>
cd CMF_XBRL

# Crear entorno virtual
python -m venv venv

# Activar (Windows)
venv\Scripts\activate

# Activar (Linux/Mac)
source venv/bin/activate

# Instalar dependencias
pip install requests beautifulsoup4 lxml pandas openpyxl pyyaml yfinance python-dotenv
```

### Variables de entorno

Crear un archivo `.env` en la raíz del proyecto:

```
CMF_API_KEY=tu_api_key_aqui
```

La API key se obtiene registrándose en [api.cmfchile.cl](https://api.cmfchile.cl/documentacion/index.html). Es necesaria únicamente para `bank_pipeline.py`.

---

## Universo de tickers

El archivo `tickers_chile.json` define el universo de empresas a analizar.

### Estructura de un ticker

```json
{
  "ticker": "FALABELLA.SN",
  "name": "Falabella S.A.",
  "categoria": "Retail",
  "flags": ["cyclical"],
  "cmf_score": 1,
  "rut": "90749000"
}
```

| Campo | Descripción |
|-------|-------------|
| `ticker` | Nemotécnico con sufijo `.SN` (Santiago) |
| `name` | Nombre legal de la empresa |
| `categoria` | Sector: Retail, Energía, Banca, Minería, etc. |
| `flags` | Etiquetas: `cyclical`, `defensive`, `commodity`, `exporter`, `regulated`, `bluechip`, `holding` |
| `cmf_score` | Calidad de reporting XBRL en CMF (1=excelente, 5=pobre) |
| `rut` | RUT chileno sin puntos ni dígito verificador |

### Agregar un ticker nuevo

1. Buscar el RUT de la empresa en [cmfchile.cl](https://www.cmfchile.cl/institucional/mercados/consulta.php?mercado=V&Estado=VI&entidad=RVEMI)
2. Agregar la entrada a `tickers_chile.json`:

```json
{
  "ticker": "NUEVATICKER.SN",
  "name": "Nueva Empresa S.A.",
  "categoria": "Sector",
  "flags": [],
  "cmf_score": 2,
  "rut": "12345678"
}
```

3. Si no conoces el RUT, ejecutar el mapeador automático:

```bash
python map_tickers.py
```

Esto genera `nemo_map.json` con los nemotécnicos extraídos de CMF y hace matching por nombre fuzzy.

### Categorías de industria

| categoria | industry (warehouse) |
|-----------|---------------------|
| Banca | `financial` |
| AFP | `financial` |
| Todo lo demás | `non_financial` |

Los tickers `financial` tienen lógica diferente en ratios de deuda y métricas bancarias.

---

## Descarga de archivos XBRL

```bash
# Solo diciembre (estados anuales) — RECOMENDADO
python -m scraper.main --year 2024 --tickers-only

# Rango de años
python -m scraper.main --year 2020 --year-end 2024 --tickers-only

# Los 4 trimestres (mar, jun, sep, dic)
python -m scraper.main --year 2024 --quarterly --tickers-only

# Universo completo CMF (~346 empresas, no solo los tickers del JSON)
python -m scraper.main --year 2024
```

### Flags importantes

| Flag | Descripción |
|------|-------------|
| `--year` | Año de inicio (obligatorio) |
| `--year-end` | Año de fin, inclusive (default: igual a `--year`) |
| `--month` | Mes específico 1–12 |
| `--quarterly` | Descarga meses 3, 6, 9, 12 |
| `--tickers-only` | Filtra al universo de `tickers_chile.json` (recomendado) |

### Salida

Los ZIPs se guardan en:
```
data/{TICKER_SN}_{rut}/{year}/{month}/{TICKER_SN}_{rut}_{year}_{month}.zip
```

Cada ZIP contiene el archivo `.xbrl` + schemas de referencia (`.xsd`, `_label.xml`, etc.).

### Al finalizar

El scraper imprime un resumen de auditoría. Los motivos de fallo típicos son:

| Razón | Causa |
|-------|-------|
| `NO_XBRL` | Empresa no publica XBRL (AFPs, fondos, Pehuenche, ZOFRI) |
| `DETAIL_ERROR` | Error HTTP al consultar el portal CMF |
| `DOWNLOAD_ERROR` | Error descargando el archivo ZIP |

---

## Parseo XBRL → facts_raw

```bash
# Parsear todos los ZIPs descargados
python xbrl_parser.py

# Solo un ticker
python xbrl_parser.py --ticker FALABELLA.SN

# Solo un año
python xbrl_parser.py --year 2024

# Sin generar Excel (más rápido)
python xbrl_parser.py --no-excel
```

### Salida

| Archivo | Descripción |
|---------|-------------|
| `output/facts_raw.csv` | Todos los facts: ~461k filas, 44 tickers, 2010–2025 |
| `output/facts_raw.xlsx` | Misma data en Excel |

### Columnas de facts_raw

| Columna | Descripción |
|---------|-------------|
| `ticker` | Nemotécnico (ej. `FALABELLA.SN`) |
| `year`, `month` | Período del reporte |
| `prefix` | `ifrs-full` o `cl-ci` |
| `concept` | Nombre del concepto XBRL (ej. `Revenue`) |
| `context_role` | `balance_current`, `balance_prev_year_end`, `period_current`, `period_prev_year` |
| `period_type` | `instant` (balance) o `duration` (P&L / CF) |
| `date` | Fecha de cierre del contexto |
| `unit` | Moneda reportada (`CLP` o `USD`) |
| `value` | Valor numérico en unidades completas |
| `value_raw` | Valor tal como aparece en el XML |

### Notas técnicas

- Los contextos se clasifican **por fecha** (no por nombre), resolviendo el cambio de IDs entre 2012 y 2013.
- El atributo `decimals` en XBRL indica **precisión de redondeo**, no un factor de escala. El valor siempre es el monto real.
- Los contextos dimensionales (segmentos, notas) se filtran — solo se conservan los 4 contextos principales del consolidado.
- Se omiten hechos sin `unitRef` (textos, fechas, porcentajes sin unidad).

---

## Warehouse financiero

El pipeline toma `facts_raw.csv` y produce un warehouse estructurado en `output/warehouse.db`.

```bash
python pipeline.py

# Sin generar CSVs individuales
python pipeline.py --no-csv

# Cambiar fuente de datos
python pipeline.py --input output/facts_raw.csv --db output/warehouse.db
```

### ¿Qué hace?

1. **Normaliza** los facts usando `concept_map.yaml` — para cada campo busca los conceptos candidatos en orden de prioridad.
2. **Detecta industria** (`financial` / `non_financial`) desde `tickers_chile.json`.
3. **Detecta moneda** (`reporting_currency`: `CLP` o `USD`) por el unit más frecuente.
4. **Calcula métricas derivadas**: `debt_total`, `net_debt`, `fcf`, `ebitda_calc`.
5. **Genera quality flags** por dimensión: `operating_expenses_quality`, `debt_quality`, `fcf_quality`.

### Concept map

El archivo `concept_map.yaml` controla qué conceptos XBRL mapean a cada campo del modelo. Para extender o ajustar:

```yaml
fields:
  revenue:
    context_role: period_current      # balance_current | period_current
    candidates:
      - ifrs-full:Revenue             # primer match gana
      - ifrs-full:RevenueFromContractsWithCustomers
      - cl-ci:RevenuesFromExternal...
    negate: false                     # true invierte el signo (ej: capex)
```

Agregar un concepto nuevo: añadir la entrada en `fields:` y re-ejecutar `pipeline.py`.

---

## Datos bancarios — API CMF

Los bancos **BCI, Santander e Itaú** no publican XBRL en el portal RVEMI. Sus estados financieros se obtienen desde la **API SBIF v3** de CMF y se integran directamente al warehouse usando el mismo esquema de tablas.

> `CHILE.SN` y `BICE.SN` sí publican XBRL y ya vienen cubiertos por `pipeline.py`.

### Ejecución normal (bancos faltantes)

```bash
# Actualizar los 3 bancos sin XBRL: BCI, BSANTANDER, ITAUCL
python bank_pipeline.py

# Solo un banco
python bank_pipeline.py --ticker BCI.SN

# Rango de años específico
python bank_pipeline.py --years 2022,2023,2024,2025

# Incluir también CHILE.SN y BICE.SN (para enriquecer campos bancarios)
python bank_pipeline.py --all-banks
```

### Cuándo ejecutar

Ejecutar `bank_pipeline.py` **después de `pipeline.py`**, ya que agrega filas al warehouse existente. El pipeline bancario hace upsert (DELETE + INSERT), por lo que re-ejecutar es seguro.

**Flujo completo de actualización anual:**

```bash
# 1. Descargar XBRL nuevos
python -m scraper.main --year 2025 --tickers-only

# 2. Parsear XBRL
python xbrl_parser.py

# 3. Reconstruir warehouse desde XBRL
python pipeline.py

# 4. Agregar / actualizar bancos desde API CMF
python bank_pipeline.py

# 5. Recalcular ratios
python ratios.py
```

### Bancos cubiertos

| Ticker | Nombre | Código CMF | Fuente | Cobertura |
|--------|--------|-----------|--------|-----------|
| `CHILE.SN` | Banco de Chile | 001 | XBRL | 2010–2025 |
| `BICE.SN` | Banco BICE | 028 | XBRL | 2011–2025 |
| `BCI.SN` | Banco de Crédito e Inversiones | 016 | API CMF | 2010–2025 |
| `BSANTANDER.SN` | Banco Santander Chile | 037 | API CMF | 2010–2025 |
| `ITAUCL.SN` | Banco Itaú Chile | 039 | API CMF | 2010–2025 |

### Campos adicionales para bancos

`bank_pipeline.py` agrega columnas específicas a `normalized_financials` que no existen para empresas no-financieras:

| Campo | Descripción |
|-------|-------------|
| `interest_income` | Ingresos por intereses (bruto) |
| `interest_expense` | Gastos por intereses |
| `net_interest_income` | Margen de intereses neto (NII) |
| `net_fee_income` | Ingresos netos por comisiones |
| `financial_assets` | Activos financieros (instrumentos + colocaciones en instrumentos) |
| `credit_loss_expense` | Gasto por pérdidas crediticias (provisiones) |

### Métricas derivadas bancarias

En `derived_metrics`:

| Campo | Fórmula | Interpretación |
|-------|---------|----------------|
| `nim` | `net_interest_income / (loans_to_customers + financial_assets)` | Net Interest Margin — rentabilidad del negocio de intermediación |
| `cost_to_income` | `(employee_benefits + depreciation) / revenue` | Eficiencia operacional. < 50% excelente |
| `credit_loss_ratio` | `credit_loss_expense / loans_to_customers` | Costo del riesgo sobre colocaciones |
| `loan_to_deposit` | `loans_to_customers / deposits_from_customers` | Uso del fondeo en préstamos |

### Ratios bancarios (en tabla `ratios`)

| Ratio | Descripción | Categoría |
|-------|-------------|-----------|
| `nim` | Net Interest Margin | profitability |
| `cost_to_income` | Ratio de eficiencia | efficiency |
| `credit_loss_ratio` | Costo del riesgo | leverage |
| `loan_to_deposit` | Ratio préstamos / depósitos | liquidity |

### Ratios excluidos para bancos

Los siguientes ratios se marcan como `not_applicable` para `industry = financial`:

`gross_margin`, `ebitda_margin`, `debt_to_equity`, `debt_to_assets`, `net_debt_to_ebitda`, `current_ratio`, `cash_ratio`, `asset_turnover`, `receivables_turnover`, `inventory_turnover`, `capex_intensity`, `fcf_margin`, `fcf_payout_ratio`, `cfo_to_net_income`, `capex_to_da`, `ev_to_ebitda`

### Esquema dual de cuentas CMF

La CMF cambió su plan de cuentas en 2022 (adopción de IFRS 9):

| Período | Formato | Escala |
|---------|---------|--------|
| 2022+ | Códigos 9 dígitos (ej. `100000000`) | Valores en CLP completo |
| Hasta 2021 | Códigos 7 dígitos (ej. `1000000`) | Valores en millones CLP |

`bank_pipeline.py` detecta el esquema automáticamente y aplica el factor de conversión correspondiente. No se requiere configuración manual.

### Nota sobre AFPs

Las AFP (PlanVital, Capital, Habitat, Provida) **no están cubiertas** por la API bancaria CMF. Reportan a la Superintendencia de Pensiones con un formato diferente. Sus filas en `tickers_chile.json` están presentes pero no tienen datos en el warehouse.

---

## Ratios

```bash
python ratios.py

# Con precios de mercado para ratios de valoración (P/E, P/B, EV/EBITDA)
python ratios.py --prices prices.csv   # CSV con columnas: ticker, year, price
```

### Ratios calculados

| Categoría | Ratios | Aplica a |
|-----------|--------|----------|
| **Profitability** | `roe`, `roe_parent`, `roa`, `ebit_margin`, `net_margin` | ambas |
| **Profitability** | `gross_margin`, `ebitda_margin` | solo `non_financial` |
| **Profitability** | `nim` | solo `financial` |
| **Leverage** | `interest_coverage`, `equity_multiplier` | ambas |
| **Leverage** | `debt_to_equity`, `debt_to_assets`, `net_debt_to_ebitda` | solo `non_financial` |
| **Leverage** | `credit_loss_ratio` | solo `financial` |
| **Liquidity** | `current_ratio`, `cash_ratio` | solo `non_financial` |
| **Liquidity** | `loan_to_deposit` | solo `financial` |
| **Efficiency** | `asset_turnover`, `receivables_turnover`, `inventory_turnover`, `capex_intensity` | solo `non_financial` |
| **Efficiency** | `cost_to_income` | solo `financial` |
| **Cash Flow** | `fcf_margin`, `fcf_payout_ratio`, `cfo_to_net_income`, `capex_to_da` | solo `non_financial` |
| **Valuation** | `pe_ratio`, `pb_ratio`, `ev_to_ebitda` *(requiere precios externos)* | ambas / `non_financial` |

### Quality flags de ratios

| Calidad | Condición |
|---------|-----------|
| `high` | Ambos componentes directo de XBRL |
| `medium` | Al menos un componente derivado (EBITDA, net_debt, FCF) |
| `low` | Dato faltante |
| `invalid` | División por cero o resultado no finito |
| `not_applicable` | Ratio no aplica a la industria |

---

## Consulta histórica por ticker

```bash
# Vista ejecutiva (métricas clave)
python query.py --ticker FALABELLA.SN

# Sección específica
python query.py --ticker FALABELLA.SN --section balance
python query.py --ticker FALABELLA.SN --section income
python query.py --ticker FALABELLA.SN --section cashflow
python query.py --ticker FALABELLA.SN --section debt
python query.py --ticker FALABELLA.SN --section ratios
python query.py --ticker FALABELLA.SN --section all

# Múltiples tickers a la vez
python query.py --ticker FALABELLA.SN,CENCOSUD.SN --section ratios

# Exportar a Excel
python query.py --ticker FALABELLA.SN --section all --format excel

# Ver todos los tickers disponibles
python query.py --list
```

### Secciones disponibles

| Sección | Contenido |
|---------|-----------|
| `summary` | P&L clave + balance clave + ratios principales |
| `balance` | Activos, pasivos y patrimonio completo |
| `income` | Estado de resultados completo |
| `cashflow` | Flujo de caja + FCF derivado |
| `debt` | Métricas de deuda y cobertura |
| `ratios` | Todos los ratios calculados |
| `all` | Todo lo anterior |

### Nota sobre moneda

Los valores monetarios se muestran en **miles de millones (B) de la moneda funcional** de la empresa:
- `CLP`: FALABELLA, CENCOSUD, ENTEL, AGUAS-A, etc.
- `USD`: COPEC, SQM, LTM, CMPC, CAP, COLBUN, VAPORES, etc.

Verificar `reporting_currency` en `normalized_financials` antes de comparar entre tickers.

---

## Validación de datos

```bash
# Generar reporte de validación (tabla para comparar manualmente)
python validate.py --format excel

# Con fetch automático desde Yahoo Finance (requiere acceso de red)
python validate.py --yfinance

# Validar tickers específicos
python validate.py --tickers FALABELLA.SN,SQM-A.SN,LTM.SN --format both
```

El reporte `output/validation_report.xlsx` contiene una hoja pivot por métrica (revenue, net_income, assets, equity, cfo) lista para comparar contra:
- **Yahoo Finance**: `https://finance.yahoo.com/quote/{TICKER}/financials/`
- **StockAnalysis**: disponible para tickers con ADR en NYSE (SQM, LTM)

### Tolerancias de validación

| Diferencia | Estado | Interpretación |
|------------|--------|----------------|
| < 1% | `match` | Diferencia de redondeo |
| 1–5% | `good` | Restatements menores |
| 5–15% | `review` | Revisar metodología o período |
| > 15% | `ALERT` | Probable error de parseo o concepto equivocado |

---

## Estructura de archivos

```
CMF_XBRL/
│
├── tickers_chile.json          # Universo de empresas a analizar
├── concept_map.yaml            # Mapeo XBRL → campos del modelo financiero
├── concept_map_banks.yaml      # Mapeo cuentas CMF API → campos del modelo (bancos)
├── .env                        # CMF_API_KEY (no incluir en git)
├── nemo_map.json               # Nemotécnico → RUT (generado por map_tickers.py)
│
├── scraper/                    # Módulo de descarga
│   ├── main.py                 # Entry point del scraper
│   ├── fetcher.py              # HTTP layer (requests + retry)
│   ├── parser.py               # Parseo HTML del portal CMF
│   ├── downloader.py           # Guardado de ZIPs
│   ├── company_index.py        # Índice RUT → nombre/ticker
│   └── logger.py               # Logging a consola + archivo
│
├── xbrl_parser.py              # Parseo XBRL → facts_raw.csv
├── pipeline.py                 # facts_raw → warehouse (3 tablas)
├── bank_pipeline.py            # API CMF → warehouse bancario (upsert)
├── ratios.py                   # Cálculo de ratios financieros (3 tablas)
├── query.py                    # Consulta histórica por ticker
├── validate.py                 # Validación vs fuentes externas
├── map_tickers.py              # Mapeo nemotécnico → RUT (helper)
│
├── data/                       # ZIPs descargados (no incluir en git)
│   ├── index.json              # Índice de empresas CMF
│   └── {TICKER}_{RUT}/
│       └── {year}/{month}/
│           └── {TICKER}_{RUT}_{year}_{month}.zip
│
├── output/                     # Outputs generados (no incluir en git)
│   ├── facts_raw.csv           # Todos los facts XBRL
│   ├── facts_raw.xlsx
│   ├── warehouse.db            # SQLite — base de datos principal
│   ├── normalized_financials.csv
│   ├── derived_metrics.csv
│   ├── quality_flags.csv
│   ├── ratios.csv
│   ├── ratio_components.csv
│   ├── ratio_quality_flags.csv
│   └── validation_report.xlsx
│
└── logs/                       # Logs de ejecución del scraper
    └── run_{timestamp}.log
```

---

## Schema del warehouse

### `normalized_financials` — 658+ filas × 62 columnas

Una fila por `(ticker, year, month)`. Valores en la moneda funcional del emisor.

> Las columnas marcadas con *(banco)* son `NULL` para empresas no-financieras. Las columnas marcadas con *(no-financiero)* son `NULL` para bancos.

**Identificadores**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `ticker` | TEXT | Nemotécnico (ej. `FALABELLA.SN`) |
| `year` | INT | Año fiscal |
| `month` | INT | Mes de cierre (casi siempre 12) |
| `industry` | TEXT | `financial` / `non_financial` |
| `reporting_currency` | TEXT | `CLP` / `USD` |

**Balance — Activos**

| Columna | Concepto XBRL base |
|---------|-------------------|
| `assets` | `Assets` |
| `current_assets` | `CurrentAssets` |
| `non_current_assets` | `NoncurrentAssets` |
| `cash` | `CashAndCashEquivalents` |
| `trade_receivables` | `TradeAndOtherCurrentReceivables` |
| `inventories` | `Inventories` |
| `ppe` | `PropertyPlantAndEquipment` |
| `intangibles` | `IntangibleAssetsAndGoodwill` |
| `goodwill` | `Goodwill` |

**Balance — Pasivos**

| Columna | Concepto XBRL base |
|---------|-------------------|
| `liabilities` | `Liabilities` |
| `current_liabilities` | `CurrentLiabilities` |
| `non_current_liabilities` | `NoncurrentLiabilities` |
| `debt_short_term` | `CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings` |
| `debt_long_term` | `LongtermBorrowings` |
| `borrowings` | `Borrowings` (total, fallback) |
| `trade_payables` | `TradeAndOtherCurrentPayables` |

**Balance — Patrimonio**

| Columna | Concepto XBRL base |
|---------|-------------------|
| `equity` | `Equity` |
| `equity_parent` | `EquityAttributableToOwnersOfParent` |
| `minority_interest` | `NoncontrollingInterests` |
| `issued_capital` | `IssuedCapital` |
| `retained_earnings` | `RetainedEarnings` |

**Estado de Resultados**

| Columna | Concepto XBRL base |
|---------|-------------------|
| `revenue` | `Revenue` |
| `cost_of_sales` | `CostOfSales` |
| `gross_profit` | `GrossProfit` |
| `distribution_costs` | `DistributionCosts` |
| `administrative_expense` | `AdministrativeExpense` |
| `other_income` | `OtherIncome` |
| `other_expense` | `OtherExpenseByFunction` |
| `employee_benefits` | `EmployeeBenefitsExpense` |
| `operating_income` | `ProfitLossFromOperatingActivities` |
| `ebit` | `ProfitLossBeforeTax` (fallback) |
| `finance_income` | `FinanceIncome` |
| `finance_costs` | `FinanceCosts` |
| `profit_before_tax` | `ProfitLossBeforeTax` |
| `income_tax` | `IncomeTaxExpenseContinuingOperations` |
| `net_income` | `ProfitLoss` |
| `net_income_parent` | `ProfitLossAttributableToOwnersOfParent` |
| `depreciation_amortization` | `DepreciationAndAmortisationExpense` |

**Flujo de Caja**

| Columna | Concepto XBRL base |
|---------|-------------------|
| `cfo` | `CashFlowsFromUsedInOperatingActivities` |
| `capex` | `PurchaseOfPPE` × -1 (positivo) |
| `investing_cf` | `CashFlowsFromUsedInInvestingActivities` |
| `dividends_paid` | `DividendsPaidClassifiedAsFinancingActivities` |
| `proceeds_from_borrowings` | `ProceedsFromBorrowingsClassifiedAsFinancingActivities` |
| `repayment_of_borrowings` | `RepaymentsOfBorrowingsClassifiedAsFinancingActivities` × -1 |
| `financing_cf` | `CashFlowsFromUsedInFinancingActivities` |
| `net_change_cash` | `IncreaseDecreaseInCashAndCashEquivalents` |

**Campos bancarios** *(solo `industry = financial`, fuente: `bank_pipeline.py`)*

| Columna | Descripción |
|---------|-------------|
| `interest_income` | Ingresos por intereses (bruto) |
| `interest_expense` | Gastos por intereses |
| `net_interest_income` | Margen de intereses neto (NII) |
| `net_fee_income` | Ingresos netos por comisiones |
| `financial_assets` | Activos financieros en instrumentos |
| `loans_to_customers` | Créditos y cuentas por cobrar a clientes |
| `deposits_from_customers` | Depósitos a la vista + depósitos a plazo |
| `credit_loss_expense` | Gasto por pérdidas crediticias (provisiones) |

**Por acción** *(no-financiero)*

| Columna | Concepto XBRL base |
|---------|-------------------|
| `eps_basic` | `BasicEarningsLossPerShare` |
| `eps_diluted` | `DilutedEarningsLossPerShare` |
| `shares_outstanding` | `NumberOfSharesOutstanding` |

---

### `derived_metrics` — 658+ filas

| Columna | Fórmula | Solo para |
|---------|---------|-----------|
| `fcf` | `cfo - capex` | `non_financial` |
| `fcf_source` | trazabilidad | — |
| `debt_total` | `debt_short + debt_long` (fallback: `borrowings`) | `non_financial` |
| `debt_total_source` | trazabilidad | — |
| `net_debt` | `debt_total - cash` | `non_financial` |
| `ebitda_calc` | `operating_income + depreciation_amortization` | `non_financial` |
| `ebitda_source` | trazabilidad | — |
| `financing_liabilities` | `deposits_from_customers` | `financial` |
| `nim` | `net_interest_income / (loans + financial_assets)` | `financial` |
| `nim_source` | trazabilidad | — |
| `cost_to_income` | `(employee_benefits + D&A) / revenue` | `financial` |
| `cost_to_income_source` | trazabilidad | — |
| `credit_loss_ratio` | `credit_loss_expense / loans_to_customers` | `financial` |
| `credit_loss_ratio_source` | trazabilidad | — |
| `loan_to_deposit` | `loans_to_customers / deposits_from_customers` | `financial` |
| `loan_to_deposit_source` | trazabilidad | — |

---

### `quality_flags` — 658+ filas

| Columna | Valores | Aplica a |
|---------|---------|----------|
| `operating_expenses_quality` | `full` / `partial` / `poor` / `not_applicable` | `non_financial` / `financial` |
| `debt_quality` | `reliable` / `proxy` / `not_applicable` / `poor` | ambas |
| `fcf_quality` | `high` / `medium` / `low` / `not_applicable` | ambas |
| `bank_data_quality` | `high` / `medium` / `poor` | `financial` |
| `interest_data_completeness` | % de campos de interés con valor | `financial` |
| `has_revenue` | bool | ambas |
| `has_assets` | bool | ambas |
| `has_equity` | bool | ambas |
| `has_operating_cf` | bool | ambas |
| `data_completeness_pct` | % de campos críticos con valor | ambas |

---

### `ratios` — 610 filas

Una fila por `(ticker, year, month)` con todos los ratios como columnas.  
Ver sección [Ratios](#ratios) para el listado completo.

---

### `ratio_components` — 26k filas

Trazabilidad de cada ratio: dos filas por `(ticker, year, ratio_name)` con numerador y denominador.

```sql
SELECT * FROM ratio_components
WHERE ticker = 'FALABELLA.SN' AND year = 2024 AND ratio_name = 'roe';
-- ratio_name | component   | field      | value       | source
-- roe        | numerator   | net_income | 635400000   | normalized_financials
-- roe        | denominator | equity     | 8441600000  | normalized_financials
```

---

### `ratio_quality_flags` — 15k filas

Una fila por `(ticker, year, ratio_name)` con la calidad del ratio.

```sql
SELECT ratio_name, quality, COUNT(*) as n
FROM ratio_quality_flags
WHERE ticker = 'FALABELLA.SN'
GROUP BY ratio_name, quality
ORDER BY ratio_name;
```

---

## Limitaciones conocidas

### Empresas sin XBRL

Las siguientes entidades no publican XBRL en el portal CMF RVEMI:

| Entidad | Razón | Solución |
|---------|-------|----------|
| **BCI, Santander, Itaú** | Norma bancaria SBIF, no IFRS RVEMI | ✅ Cubiertos por `bank_pipeline.py` vía API CMF |
| **AFPs** (Capital, Habitat, PlanVital, Provida) | Reportan a Superintendencia de Pensiones | ❌ Sin cobertura (fuente separada requerida) |
| **ZOFRI, Pehuenche** | No sujetos a norma IFRS obligatoria | ❌ Sin datos |
| **CFINRENTAS** | Fondo de inversión, sin RUT de emisor | ❌ Sin datos |

`CHILE.SN` (Banco de Chile) y `BICE.SN` (BICECORP holding) sí publican XBRL y están cubiertos por `pipeline.py`.

### Cobertura temporal

- **2010–2011**: Solo ~39 de 55 tickers tienen XBRL (resto publicó PDFs en ese período).
- **2012+**: Cobertura completa para los tickers con XBRL.

### Moneda mixta

Empresas como `ENELAM.SN` tienen algunos años en CLP y otros en USD. El campo `reporting_currency` refleja la moneda del año específico.

### Deuda financiera

El campo `debt_total` tiene cobertura del ~37% porque:
- Los bancos no usan el concepto `Borrowings` (usan depósitos de clientes)
- Algunos holdings reportan deuda bajo conceptos no estándar

### EBITDA

`ebitda_calc` es siempre derivado (`operating_income + D&A`). Algunas empresas de Energía y Utilities reportan D&A de forma separada que puede no coincidir exactamente con las notas del reporte anual.

### Datos trimestrales

El scraper descarga por defecto solo **diciembre** (estados anuales). Para trimestres usar `--quarterly`. Los datos trimestrales no son acumulados en el pipeline actual — cada trimestre es un row independiente.
