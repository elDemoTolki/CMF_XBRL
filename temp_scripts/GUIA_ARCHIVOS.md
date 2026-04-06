# Guía de Archivos - Financial Data Warehouse

**Fecha actualización**: 2026-04-05 13:49

---

## 📚 Resumen Ejecutivo

Tienes **2 bases de datos** y **múltiples archivos CSV**. Solo **warehouse.db está actualizado** con datos corregidos.

---

## 1. BASES DE DATOS

### 🗄️ **warehouse.db** ← **ESTE ES EL MASTER DATA**
- **Tamaño**: 4.0 MB
- **Última actualización**: HOY (2026-04-05 13:42)
- **Estado**: ✅ **ACTUALIZADO con datos corregidos**
- **Origen**: Generado por `pipeline.py`, `ratios.py` y correcciones manuales

**Tablas (6):**
| Tabla | Registros | Descripción |
|-------|-----------|-------------|
| `normalized_financials` | 658 | Estados financieros normalizados (Balance, P&L, Cash Flow) |
| `derived_metrics` | 658 | Métricas calculadas (FCF, deuda, EBITDA) |
| `quality_flags` | 658 | Flags de calidad de datos |
| `ratios` | 658 | **Ratios financieros calculados** ✓ |
| `ratio_components` | 26,582 | Componentes de ratios (trazabilidad) |
| `ratio_quality_flags` | 19,082 | Calidad de ratios |

**✅ Contiene datos CORREGIDOS:**
- CHILE.SN (8 años corregidos desde Excel)
- CENCOSUD.SN (7 años corregidos desde Excel)
- MALLPLAZA.SN (8 años corregidos desde Excel)
- 44 empresas más con datos XBRL confiables

---

### 🗄️ **financials.db** ← **OBSOLETO - NO USAR**
- **Tamaño**: 156 KB
- **Última actualización**: 2026-04-02 21:17
- **Estado**: ❌ **DESACTUALIZADO** - contiene datos INCORRECTOS
- **Origen**: Desconocido (posiblemente script antiguo `query.py`)

**Problema:**
```
CHILE.SN 2024 en financials.db:
  assets = 801,845,962 (INCORRECTO - dato antiguo de XBRL)

CHILE.SN 2024 en warehouse.db:
  assets = 52,095,441,000,000 (CORRECTO - dato del Excel)
```

**🎯 Recomendación**: ELIMINAR este archivo para evitar confusión

---

## 2. ARCHIVOS CSV

### ✅ **CSVs ACTUALIZADOS** (recién generados HOY)
- **Fecha**: 2026-04-05 13:49
- **Fuente**: Exportados desde `warehouse.db` con datos CORREGIDOS

| Archivo | Filas | Estado |
|---------|-------|--------|
| `normalized_financials.csv` | 658 | ✅ Datos CORREGIDOS |
| `derived_metrics.csv` | 658 | ✅ Actualizado |
| `quality_flags.csv` | 658 | ✅ Actualizado |
| `ratios.csv` | 658 | ✅ Ratios recalculados HOY |

**Qué contiene cada CSV:**

#### `normalized_financials.csv`
Una fila por `(ticker, year, month)` con 62 columnas:
- **Identificación**: ticker, year, month, industry, reporting_currency
- **Balance**: assets, liabilities, equity, cash, inventories, etc.
- **Estado de Resultados**: revenue, net_income, operating_income, etc.
- **Flujo de Caja**: cfo, capex, fcf, dividends_paid
- **Bancos** (solo financial): loans_to_customers, deposits_from_customers, etc.

#### `ratios.csv`
Una fila por `(ticker, year, month)` con ratios calculados:
- **Profitability**: roe, roa, net_margin, ebit_margin
- **Liquidity**: current_ratio, cash_ratio
- **Leverage**: debt_to_equity, debt_to_assets
- **Efficiency**: asset_turnover, inventory_turnover
- **Cash Flow**: fcf_margin, cfo_to_net_income

---

## 3. ¿CÓMO SE GENERAN?

### Flujo de Generación

```
┌─────────────────────────────────────────────────────────────┐
│ 1. XBRL CMF → xbrl_parser.py → output/facts_raw.csv         │
│    (505 MB - TODOS los facts XBRL)                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. pipeline.py → output/warehouse.db + CSVs                │
│    (Normaliza, deriva, quality flags)                       │
│    - normalized_financials (658 filas)                     │
│    - derived_metrics (658 filas)                           │
│    - quality_flags (658 filas)                             │
│    - CSVs exportados si NO es --no-csv                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ratios.py → output/warehouse.db (tabla ratios) + CSV      │
│    (Calcula ratios financieros)                             │
│    - ratios (658 filas)                                     │
│    - ratio_components (26,582 filas)                       │
│    - ratio_quality_flags (19,082 filas)                    │
│    - CSV exportado                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Correcciones manuales → warehouse.db                    │
│    - CHILE.SN cargado desde Excel (8 años)                 │
│    - CENCOSUD.SN cargado desde Excel (7 años)               │
│    - MALLPLAZA.SN cargado desde Excel (8 años)              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. exportar_csv_actualizados.py → CSVs ACTUALIZADOS        │
│    (Regenera CSVs desde warehouse.db)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. ESTADO ACTUAL DE ARCHIVOS

### ✅ **ACTUALIZADOS HOY (2026-04-05 13:49)**

| Archivo | Tamaño | Estado |
|---------|--------|--------|
| **warehouse.db** | 4.0 MB | ✅ **MASTER DATA - Datos CORREGIDOS** |
| **normalized_financials.csv** | 268 KB | ✅ Exportado HOY desde warehouse.db |
| **ratios.csv** | 263 KB | ✅ Exportado HOY (ratios recalculados) |
| **derived_metrics.csv** | 60 KB | ✅ Exportado HOY |
| **quality_flags.csv** | 47 KB | ✅ Exportado HOY |

### ❌ **DESACTUALIZADOS (NO USAR)**

| Archivo | Tamaño | Fecha | Problema |
|---------|--------|--------|----------|
| `financials.db` | 156 KB | Apr 2 | Datos INCORRECTOS de XBRL antiguo |
| `facts_raw.csv` | 505 MB | Apr 2 | Demasiado grande, solo referencia |

---

## 5. RESPUESTAS A TUS PREGUNTAS

### ❓ **¿Qué información tiene warehouse.db?**

**Respuesta**: Es la **"Master Data" confiable** con:
- **47 empresas** chilenas listadas en bolsa
- **658 registros** financieros (períodos ticker-año-mes)
- **Cobertura 2010-2025** (16 años de datos históricos)
- **3 empresas corregidas** con datos manuales confiables
- **4,956 ratios financieros** calculados
- **62 columnas** de métricas financieras por registro

### ❓ **¿Qué información tiene financials.db?**

**Respuesta**: Es una base de datos **OBSOLETA** con:
- **610 registros** en una sola tabla llamada "financials"
- **Datos INCORRECTOS** de XBRL (ej: CHILE.SN con assets mal reportados)
- **Origen desconocido**, probablemente generado por un script antiguo
- **NO se mantiene actualizado**

**🎯 Recomendación**: Eliminar este archivo para evitar confusión

### ❓ **¿Se generan desde warehouse?**

**Respuesta**:

**✅ SÍ - Los CSV ACTUALES se generaron HOY desde warehouse.db:**
```bash
python exportar_csv_actualizados.py  # Ejecutado hoy 13:49
```

**❌ NO - financials.db NO se genera desde warehouse:**
- Es una base de datos independiente antigua
- Tiene estructura diferente
- Contiene datos desactualizados

### ❓ **¿Qué información maneja ratios.csv?**

**Respuesta**: Contiene **4,956 ratios financieros** calculados a partir de warehouse.db:

**Categorías de ratios:**
- **Profitability**: ROE, ROA, Net Margin, EBIT Margin, Gross Margin
- **Liquidity**: Current Ratio, Quick Ratio, Cash Ratio
- **Leverage**: Debt-to-Equity, Debt-to-Assets
- **Efficiency**: Asset Turnover, Inventory Turnover, Receivables Turnover
- **Cash Flow**: FCF Margin, CFO/Net Income, Capex/Depreciation

**Ejemplo de datos:**
```
ticker       year  roe(%)  net_margin(%)  current_ratio  debt_to_equity
CENCOSUD.SN  2024  9.44    0.76          1.77x          calculado
MALLPLAZA.SN  2024  10.81   0.69          1.18x          calculado
CHILE.SN      2024  N/A     N/A           N/A            (financiera)
```

### ❓ **¿Están actualizados?**

**Respuesta**: 

| Archivo | Actualizado | Datos Corregidos |
|---------|-------------|------------------|
| **warehouse.db** | ✅ HOY 13:42 | ✅ SÍ (CHILE, CENCOSUD, MALLPLAZA) |
| **normalized_financials.csv** | ✅ HOY 13:49 | ✅ SÍ (exportado desde warehouse) |
| **ratios.csv** | ✅ HOY 13:49 | ✅ SÍ (recalculados HOY) |
| **derived_metrics.csv** | ✅ HOY 13:49 | ✅ SÍ |
| **quality_flags.csv** | ✅ HOY 13:49 | ✅ SÍ |
| **financials.db** | ❌ Abr 2 | ❌ NO (datos incorrectos) |

---

## 6. 🎯 CONCLUSIÓN Y RECOMENDACIONES

### ✅ **Usar warehouse.db como única fuente de verdad**

Es la **"Master Data"** con:
- Datos históricos validados (2010-2025)
- Empresas corregidas con datos confiables
- Ratios calculados correctamente
- Mantenimiento programado para años futuros

### ❌ **Eliminar financials.db**

```bash
rm output/financials.db
```

Contiene datos obsoletos y genera confusión.

### 📊 **Los CSV son solo para exportación**

No se usan internamente. Son archivos de conveniencia para:
- Análisis en Excel
- Visualización rápida
- Intercambio con otros sistemas

**La fuente de verdad SIEMPRE es warehouse.db**

---

## 7. 🔧 Scripts Útiles

| Script | Propósito |
|--------|-----------|
| `exportar_csv_actualizados.py` | Regenera CSV desde warehouse.db |
| `recalcular_ratios.py` | Recalcula ratios sin pandas |
| `validate_excel_planilla.py` | Valida warehouse vs Excel manual |
| `reporte_completitud_v2.py` | Analiza completitud por ticker y año |

---

## 8. 📊 Documentación de Validación y Completitud

| Archivo | Propósito |
|--------|-----------|
| `VALIDACION.md` | Reporte completo de validación vs Excel |
| `TABLA_COMPLETITUD.md` | Tabla detallada de completitud por ticker/año |
| `RESUMEN_COMPLETITUD.md` | Resumen ejecutivo de completitud |

**Estado de Completitud (2026-04-05):**
- **46/47 tickers (97.9%)** con 100% de años completos
- **Financial**: 4/5 bancos completos (CHILE.SN parcial)
- **Non-financial**: 42/42 empresas completas

---

**Última actualización**: 2026-04-05
**Estado**: ✅ Warehouse validado y listo para producción
