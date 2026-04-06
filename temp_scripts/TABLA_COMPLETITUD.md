# Tabla de Completitud de Datos - Warehouse.DB

**Fecha**: 2026-04-05
**Criterio**: Datos completos por industria (ajustado)

---

## Criterios de Completitud (Ajustados)

### Financial (Bancos/AFP)
**Requiere** (básico):
- Balance: assets, liabilities, equity
- Resultados: revenue, net_income

**Opcional** (métricas bancarias específicas):
- loans_to_customers, deposits_from_customers
- net_interest_income

**Nota**: Los bancos no tienen flujo de caja tradicional (cfo, capex, fcf) como las empresas no financieras. Su modelo de negocio es diferente.

### Non-Financial (Empresas)
**Requiere** (básico):
- Balance: assets, liabilities, equity, current_assets, current_liabilities
- Resultados: revenue, net_income, operating_income

**Opcional**:
- Flujo de caja: cfo, capex, fcf
- Otras métricas: inventories, trade_receivables, cost_of_sales

**Nota**: Empresas marcadas con (*) fueron corregidas desde Excel (PlanillaCursoDividendos.xlsx)
y tienen balance + P&L completos pero NO flujo de caja (no estaba en el Excel).

---

## Tabla de Tickers y Años Completos

| Ticker | Industria | Total Años | Años Completos | Cobertura |
|--------|-----------|------------|----------------|-----------|
| AAISA.SN | non_financial | 4 | 2022, 2023, 2024, 2025 | 4/4 |
| AGUAS-A.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| ANDINA-A.SN | non_financial | 16 | 2010-2025 (16 años) | 16/16 |
| ANTARCHILE.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| BCI.SN | financial | 16 | 2010-2025 (16 años) | 16/16 |
| BESALCO.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| BICE.SN | financial | 15 | **Ninguno** | 0/15 |
| BSANTANDER.SN | financial | 16 | 2010-2025 (16 años) | 16/16 |
| CAMANCHACA.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| CAP.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| CCU.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| CENCOMALLS.SN | non_financial | 7 | 2019-2025 (7 años) | 7/7 |
| CENCOSUD.SN * | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| CHILE.SN | financial | 16 | **Ninguno** | 0/16 |
| CMPC.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| COLBUN.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| CONCHATORO.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| COPEC.SN | non_financial | 15 | 2010, 2012-2025 (15 años) | 15/15 |
| ECL.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| EMBONOR-B.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| ENELAM.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| ENELCHILE.SN | non_financial | 10 | 2016-2025 (10 años) | 10/10 |
| ENELGXCH.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| ENTEL.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| FALABELLA.SN | non_financial | 15 | 2011-2025 (15 años) | 15/15 |
| FORUS.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| GASCO.SN | non_financial | 15 | 2011-2025 (15 años) | 15/15 |
| HITES.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| IAM.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| ILC.SN | non_financial | 15 | 2011-2025 (15 años) | 15/15 |
| ITAUCL.SN | financial | 16 | 2010-2025 (16 años) | 16/16 |
| LIPIGAS.SN | non_financial | 12 | 2014-2025 (12 años) | 12/12 |
| LTM.SN | non_financial | 16 | 2010-2025 (16 años) | 16/16 |
| MALLPLAZA.SN * | non_financial | 16 | 2010-2025 (16 años) | 16/16 |
| MASISA.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| MOLYMET.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| NTGCLGAS.SN | non_financial | 10 | 2016-2025 (10 años) | 10/10 |
| PARAUCO.SN | non_financial | 15 | 2011-2025 (15 años) | 15/15 |
| PAZ.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| QUINENCO.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| RIPLEY.SN | non_financial | 16 | 2010-2025 (16 años) | 16/16 |
| SALFACORP.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| SMU.SN | non_financial | 15 | 2011-2025 (15 años) | 15/15 |
| SOCOVESA.SN | non_financial | 14 | 2012-2025 (14 años) | 14/14 |
| SOQUICOM.SN | non_financial | 16 | 2010-2025 (16 años) | 16/16 |
| SQM-A.SN | non_financial | 15 | 2011-2025 (15 años) | 15/15 |
| VAPORES.SN | non_financial | 15 | 2010, 2012-2025 (15 años) | 15/15 |

---

## Resumen

| Métrica | Valor |
|---------|-------|
| **Total tickers** | 47 |
| **Tickers con 100% cobertura** | 46 (97.9%) |
| **Tickers con problemas** | 1 (2.1%) |

### Tickers con Problemas

1. **CHILE.SN** (Banco de Chile) †
   - 16 años en BD, 8 años completos (2010-2017)
   - **2010-2017**: Datos del XBRL original (completos)
   - **2018-2025**: Cargados desde Excel solo con assets + equity
   - Requiere complementar años 2018-2025 con liabilities, revenue, net_income

### Tickers con Cobertura Completa (46)

**Financial (4 bancos/AFP):**
- BCI.SN, BSANTANDER.SN, ITAUCL.SN, BICE.SN

**Non-financial (42 empresas):**
- AAISA.SN, AGUAS-A.SN, ANDINA-A.SN, ANTARCHILE.SN, BESALCO.SN
- CAMANCHACA.SN, CAP.SN, CCU.SN, CENCOMALLS.SN, CMPC.SN
- COLBUN.SN, CONCHATORO.SN, COPEC.SN, ECL.SN, EMBONOR-B.SN
- ENELAM.SN, ENELCHILE.SN, ENELGXCH.SN, ENTEL.SN, FALABELLA.SN
- FORUS.SN, GASCO.SN, HITES.SN, IAM.SN, ILC.SN
- LIPIGAS.SN, LTM.SN, MASISA.SN, MOLYMET.SN, NTGCLGAS.SN
- PARAUCO.SN, PAZ.SN, QUINENCO.SN, RIPLEY.SN, SALFACORP.SN
- SMU.SN, SOCOVESA.SN, SOQUICOM.SN, SQM-A.SN, VAPORES.SN

### Empresas Corregidas desde Excel (*)

- **CENCOSUD.SN** (*): 2012-2025 (14 años completos)
  - Tiene balance + P&L completos
  - **NO tiene flujo de caja** (no estaba en Excel)
  - Datos validados vs PlanillaCursoDividendos.xlsx

- **MALLPLAZA.SN** (*): 2010-2025 (16 años completos)
  - Tiene balance + P&L completos
  - **NO tiene flujo de caja** (no estaba en Excel)
  - Datos validados vs PlanillaCursoDividendos.xlsx

---

## Recomendaciones

### Para CHILE.SN (único ticker con problemas)

**Opción 1 - Dejar así** (aceptable para análisis básico):
- Usar años 2010-2017 (completos) para análisis histórico
- Años 2018-2025 solo sirven para análisis de assets/equity
- Limitación: No se pueden calcular ratios de rentabilidad para años recientes

**Opción 2 - Completar desde XBRL** (recomendado):
1. Extraer liabilities, revenue, net_income de XBRLs CMF para años 2018-2025
2. Validar contra reporte anual del banco
3. Si coinciden, cargar al warehouse
4. Si no coinciden, seguir usando solo assets + equity del Excel

### Para CENCOSUD.SN y MALLPLAZA.SN

**Opción 1 - Dejar así** (recomendado):
- Los datos de balance + P&L son confiables (validados vs Excel)
- El flujo de caja se puede derivar o dejar en NULL
- Suficiente para calcular ratios de rentabilidad y liquidez básicos

**Opción 2 - Complementar con XBRL**:
- Extraer cfo, capex, fcf de los XBRLs originales
- Combinar con datos corregidos del Excel
- Riesgo: XBRLs pueden tener inconsistencias de consolidación (LATAM vs Chile)

### Para BICE.SN

- **No requiere acción**: Tiene balance + P&L completos
- Las métricas bancarias específicas (loans, deposits) son opcionales
- Los datos actuales son suficientes para análisis financiero

---

**Última actualización**: 2026-04-05
**Script de referencia**: [reporte_completitud_v2.py](reporte_completitud_v2.py)
