# 📊 Análisis de Integración - Dividend History (Yahoo Finance)

**Fecha:** 2025-01-06
**Fuente:** Yahoo Finance - Dividend Events
**Total eventos:** 964 dividendos para 54/55 tickers
**Rango:** 2016 - 2026

---

## Resumen Ejecutivo

**Recomendación:** ✅ **ALTA VALOR - INTEGRAR AL WAREHOUSE**

Los datos de dividendos de Yahoo Finance son **altamente complementarios** a los datos existentes del warehouse y proporcionan información que NO está disponible actualmente.

---

## 📋 Estructura de los Datos

### Tabla Propuesta: `dividend_history`

```sql
CREATE TABLE dividend_history (
  ticker TEXT NOT NULL,              -- e.g., 'SQM-A.SN'
  year INTEGER NOT NULL,             -- Year of ex-date
  month INTEGER NOT NULL,            -- Month of ex-date (1-12)
  day INTEGER NOT NULL,              -- Day of ex-date
  amount REAL NOT NULL,              -- Dividend amount per share (CLP)
  currency TEXT NOT NULL DEFAULT 'CLP',
  data_source TEXT NOT NULL DEFAULT 'yahoo_finance',
  extracted_at TEXT NOT NULL,        -- ISO timestamp of extraction
  PRIMARY KEY (ticker, year, month, day)
);
```

---

## 🆚 Comparación con Datos Existentes del Warehouse

### Warehouse Actual (`normalized_financials`)

| Campo | Descripción | Frecuencia | Unidad |
|-------|-------------|------------|--------|
| `dividends_paid` | **Total** dividends pagados por la empresa | Anual | CLP (total) |
| `net_income` | Utilidad neta | Anual | CLP |
| `year`, `month` | Periodo fiscal | Anual (mes=12) | - |

### Yahoo Finance (`dividend_history`)

| Campo | Descripción | Frecuencia | Unidad |
|-------|-------------|------------|--------|
| `amount` | **Per share** dividend por acción | Por evento | CLP/acción |
| `year`, `month`, `day` | Fecha ex-dividendo | Evento individual | - |
| `ticker` | Símbolo | - | - |

---

## ✅ Beneficios de la Integración

### 1. **Datos Complementarios (NO Duplicados)**

**Warehouse:** `dividends_paid` = Total pagado por la empresa (todos los shares)
**Yahoo:** `amount` = Dividend por acción individual

**Relación:**
```
dividends_paid (warehouse) ≈ Σ amount (Yahoo) × shares_outstanding
```

**Ejemplo CENCOSUD.SN 2022:**
- Yahoo: 127.0 CLP/share
- Warehouse: 361,442M CLP total
- Shares: ~2,846M
- Validación: 127.0 × 2,846M ≈ 361B CLP ✅

### 2. **Granularidad Temporal**

**Warehouse:** Datos anuales agregados
**Yahoo:** Fecha exacta de cada pago (día/mes/año)

**Usos:**
- Análisis de frecuencia de pagos (mensual, trimestral, semestral, anual)
- Identificación de patrones de pago
- Timing de cash flows para inversionistas

### 3. **Historial Completo 2016-2026**

**Warehouse actual:** 2010-presente (con gaps)
**Yahoo:** 2016-2026 (10+ años, más completo para algunos tickers)

**Ventaja:**
- Llenar gaps en datos históricos
- Validar datos existentes del warehouse
- Identificar missing data en warehouse

### 4. **Análisis de Consistencia de Dividendos**

**Posibles queries:**
```sql
-- Empresas que han pagado dividends todos los años (Dividend Aristocrats)
SELECT ticker, COUNT(DISTINCT year) as years_paid
FROM dividend_history
WHERE year BETWEEN 2016 AND 2025
GROUP BY ticker
HAVING years_paid = 10
ORDER BY ticker;

-- Frecuencia de pagos por ticker
SELECT
  ticker,
  COUNT(*) as total_events,
  COUNT(DISTINCT year) as years,
  ROUND(CAST(COUNT(*) AS FLOAT) / COUNT(DISTINCT year), 1) as frequency_per_year
FROM dividend_history
GROUP BY ticker
ORDER BY frequency_per_year DESC;

-- Crecimiento de dividendos (CAGR)
SELECT
  ticker,
  MIN(amount) as first_dividend,
  MAX(amount) as last_dividend,
  ROUND((POWER(CAST(MAX(amount) AS FLOAT) / MIN(amount), 1.0/9.0) - 1) * 100, 2) as cagr_pct
FROM dividend_history
WHERE year IN (2016, 2025)
GROUP BY ticker
HAVING first_dividend > 0
ORDER BY cagr_pct DESC;
```

### 5. **Validación Cruzada de Datos**

**Cross-check entre warehouse y Yahoo:**
```sql
-- Comparar dividends_paid (warehouse) vs Σ(amount × shares) (Yahoo)
SELECT
  nf.ticker,
  nf.year,
  nf.dividends_paid as warehouse_total,
  SUM(dh.amount) as yahoo_total_per_share,
  -- Asumiendo shares_outstanding disponible
  (nf.dividends_paid / 2846000000) as implied_per_share
FROM normalized_financials nf
LEFT JOIN dividend_history dh ON nf.ticker = dh.ticker AND nf.year = dh.year
WHERE nf.ticker = 'CENCOSUD.SN' AND nf.year = 2022
GROUP BY nf.ticker, nf.year;
```

---

## 📊 Cobertura de Tickers

### Tickers con Datos en Ambas Fuentes: 54/55

**Ticker sin dividendos en Yahoo:**
- **BICE:** 0 eventos (¿No paga dividendos desde 2016? Requiere verificación manual)

### Top Tickers por Eventos de Dividendos

| Ticker | Eventos | Años | Frecuencia Típica |
|--------|---------|------|-------------------|
| **GASCO** | 57 | 2016-2026 | Mensual |
| **LIPIGAS** | 46 | 2016-2026 | Cuatrimestral |
| **SQM-A, SQM-B** | 30 | 2016-2024 | Cuatrimestral |
| **PEHUENCHE** | 31 | 2016-2026 | Semestral |
| **ANDINA-B** | 38 | 2016-2025 | Semestral |
| **CONCHATORO** | 38 | 2016-2026 | Semestral |
| **HABITAT** | 28 | 2016-2026 | Semestral |

### Frecuencias de Pago Identificadas

- **Mensual:** GASCO (57 eventos en 10 años)
- **Cuatrimestral:** LIPIGAS, SQM-A/B (~3 eventos/año)
- **Semestral:** Most common (AGUAS-A, CCU, CMPC, COLBUN, etc.)
- **Anual:** BCI, CAP, COPEC, FALABELLA, etc.

---

## 🔧 Pasos para Integración

### Opción 1: Usar Script SQL (Recomendado)

```bash
# 1. Copiar el archivo SQL al repo CMF_XBRL
cp G:\Code\Porfolio\portfolio-tracker\data\dividend_export\dividend_history.sql G:\Code\CMF_XBRL\data\

# 2. Ejecutar el script en el warehouse
cd G:\Code\CMF_XBRL
sqlite3 output/warehouse.db < data/dividend_history.sql

# 3. Validar la carga
sqlite3 output/warehouse.db "SELECT COUNT(*) FROM dividend_history;"
# Debe mostrar: 964
```

### Opción 2: Usar el CSV

```bash
# 1. Copiar el CSV
cp G:\Code\Porfolio\portfolio-tracker\data\dividend_export\dividend_history.csv G:\Code\CMF_XBRL\data\

# 2. Importar usando SQLite
sqlite3 output/warehouse.db
.mode csv
.import data/dividend_history.csv dividend_history
```

### Validación Post-Carga

```sql
-- Verificar cantidad de registros
SELECT COUNT(*) FROM dividend_history;
-- Expected: 964

-- Verificar distribución por ticker
SELECT ticker, COUNT(*) as events
FROM dividend_history
GROUP BY ticker
ORDER BY events DESC
LIMIT 10;

-- Verificar rangos de fechas
SELECT
  MIN(year) || '-' || MAX(year) as year_range,
  COUNT(DISTINCT ticker) as tickers
FROM dividend_history;

-- Verificar un ticker específico
SELECT * FROM dividend_history WHERE ticker = 'CENCOSUD.SN' ORDER BY year, month, day;
```

---

## 🎯 Casos de Uso

### 1. **Análisis de Dividend Yield**

```sql
-- Dividend yield actual (último dividend / precio spot)
SELECT
  dh.ticker,
  dh.amount as last_dividend,
  -- JOIN con tabla de precios (si está disponible)
  -- sp.spot_price,
  -- (dh.amount / sp.spot_price * 100) as dividend_yield_pct
FROM dividend_history dh
INNER JOIN (
  SELECT ticker, MAX(year || '-' || month || '-' || day) as last_date
  FROM dividend_history
  GROUP BY ticker
) latest ON dh.ticker = latest.ticker
ORDER BY dh.amount DESC;
```

### 2. **Identificar Dividend Aristocrats**

```sql
-- Empresas que han aumentado o mantenido dividends por 10+ años
WITH yearly_dividends AS (
  SELECT
    ticker,
    year,
    SUM(amount) as annual_dividend
  FROM dividend_history
  WHERE year BETWEEN 2016 AND 2025
  GROUP BY ticker, year
),
dividend_growth AS (
  SELECT
    ticker,
    FIRST_VALUE(annual_dividend) OVER (PARTITION BY ticker ORDER BY year) as first_year_div,
    LAST_VALUE(annual_dividend) OVER (PARTITION BY ticker ORDER BY year) as last_year_div
  FROM yearly_dividends
)
SELECT
  ticker,
  first_year_div,
  last_year_div,
  ROUND((CAST(last_year_div AS FLOAT) / first_year_div - 1) * 100, 2) as growth_pct
FROM dividend_growth
GROUP BY ticker
HAVING COUNT(DISTINCT year) = 10  -- 10 años completos
  AND last_year_div >= first_year_div  -- No decrecimiento
ORDER BY growth_pct DESC;
```

### 3. **Validar Datos del Warehouse**

```sql
-- Comparar warehouse dividends vs Yahoo dividends (sumarizado por año)
SELECT
  nf.ticker,
  nf.year,
  nf.dividends_paid as warehouse_div,
  SUM(dh.amount) as yahoo_div_per_share,
  -- Calcular shares implícitos
  (nf.dividends_paid / NULLIF(SUM(dh.amount), 0)) as implied_shares
FROM normalized_financials nf
LEFT JOIN dividend_history dh ON nf.ticker = dh.ticker AND nf.year = dh.year
WHERE nf.dividends_paid IS NOT NULL
  AND nf.year BETWEEN 2020 AND 2024
GROUP BY nf.ticker, nf.year, nf.dividends_paid
ORDER BY nf.ticker, nf.year;
```

---

## ⚠️ Consideraciones y Limitaciones

### 1. **Ticker BICE sin Dividendos**
- **BICE:** 0 eventos en Yahoo (2016-2026)
- **Posibles causas:**
  - No paga dividendos desde 2016
  - Yahoo Finance no tiene datos
  - Ticker incorrecto en Yahoo
- **Acción:** Verificar manualmente si BICE paga dividendos

### 2. **Unidades Diferentes**
- **Warehouse:** `dividends_paid` en CLP total
- **Yahoo:** `amount` en CLP per share
- **Requiere:** `shares_outstanding` para comparación directa

### 3. **Fechas Ex-Dividend vs Pago**
- **Yahoo:** Fecha ex-dividend (cuando el precio ajusta)
- **Warehouse:** Periodo fiscal (cuando se pagó)
- **Diferencia:** Puede haber lag de 1-2 meses entre fecha ex y pago

### 4. **Dividendos Especiales**
- Yahoo puede incluir dividendos especiales one-time
- Warehouse `dividends_paid` incluye todo
- Puede haber diferencias por ajustes o dividendos extraordinarios

---

## 📈 Impacto en Portfolio Tracker

### Beneficios para el Portfolio Tracker:

1. **Dividend Yield Histórico**
   - Calcular yield para cualquier fecha histórica
   - Analizar tendencia de yield a través del tiempo

2. **Proyección de Dividendos**
   - Usar histórico para estimar dividendos futuros
   - Identificar patrones estacionales

3. **Análisis de Retorno Total**
   - Price appreciation + Dividend reinvestment
   - Comparar vs índices benchmark

4. **Filtros de Selección**
   - Solo empresas con 10+ años de dividendos crecientes
   - Min dividend yield > X%
   - Max payout ratio < Y%

---

## 🚀 Recomendación Final

### ✅ **INTEGRAR - ALTA PRIORIDAD**

**Razones:**
1. Datos complementarios (NO duplicados)
2. Granularidad temporal no disponible en warehouse
3. Historial completo 2016-2026
4. Habilita análisis avanzados de dividendos
5. Validación cruzada de datos warehouse
6. Single source of truth (warehouse + dividend history)

**Próximos pasos:**
1. ✅ Ejecutar script SQL para crear tabla `dividend_history`
2. ✅ Validar carga (964 registros)
3. ✅ Verificar consistencia con datos warehouse
4. ✅ Documentar queries de análisis
5. ✅ Actualizar portfolio tracker para usar nueva tabla

**Archivos listos:**
- `G:\Code\Porfolio\portfolio-tracker\data\dividend_export\dividend_history.sql`
- `G:\Code\Porfolio\portfolio-tracker\data\dividend_export\dividend_history.csv`
- `G:\Code\Porfolio\portfolio-tracker\data\dividend_export\dividend_summary_by_ticker.txt`

---

**Última actualización:** 2025-01-06
**Estado:** ✅ LISTO PARA INTEGRAR - Recomendado proceder
