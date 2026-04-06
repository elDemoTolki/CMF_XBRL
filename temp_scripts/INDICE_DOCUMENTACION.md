# Índice de Documentación - CMF XBRL Financial Data Warehouse

**Última actualización**: 2026-04-05
**Estado del proyecto**: ✅ Validado y listo para producción

---

## 📖 Documentación Principal

### Para usuarios nuevos
1. **[README.md](README.md)** - Guía completa del usuario
   - Arquitectura del sistema
   - Instrucciones de instalación y uso
   - Flujos de trabajo comunes
   - Estado de validación y limitaciones

### Para análisis de datos
2. **[RESUMEN_COMPLETITUD.md](RESUMEN_COMPLETITUD.md)** - Resumen ejecutivo
   - Estado de completitud: 46/47 tickers (97.9%)
   - Casos especiales y recomendaciones
   - Métricas de calidad

3. **[TABLA_COMPLETITUD.md](TABLA_COMPLETITUD.md)** - Tabla detallada
   - Completitud por ticker y año
   - Criterios por industria
   - Empresas corregidas desde Excel

### Para validación de datos
4. **[VALIDACION.md](VALIDACION.md)** - Reporte de validación completo
   - Proceso de validación vs Excel manual
   - Empresas corregidas (CHILE.SN, CENCOSUD.SN, MALLPLAZA.SN)
   - Resultados y recomendaciones

### Para referencia técnica
5. **[architecture.md](architecture.md)** - Documentación técnica detallada
   - Arquitectura de componentes
   - Schema de base de datos
   - Estrategias de manejo de errores
   - Diccionario de datos

6. **[agent.md](agent.md)** - Directrices de desarrollo
   - Reglas de desarrollo
   - Stack tecnológico
   - Criterios de aceptación

### Para gestión de archivos
7. **[GUIA_ARCHIVOS.md](GUIA_ARCHIVOS.md)** - Guía de archivos y bases de datos
   - Estructura de directorios
   - Descripción de bases de datos (warehouse.db vs financials.db)
   - Scripts útiles

---

## 🗂️ Estructura de Archivos

```
CMF_XBRL/
│
├── Documentación principal
│   ├── README.md                    # Guía de usuario (v4.1)
│   ├── architecture.md              # Documentación técnica
│   ├── agent.md                     # Directrices de desarrollo
│   │
├── Documentación de datos
│   ├── GUIA_ARCHIVOS.md             # Guía de archivos y BD
│   ├── VALIDACION.md                # Reporte de validación
│   ├── TABLA_COMPLETITUD.md         # Tabla de completitud
│   ├── RESUMEN_COMPLETITUD.md       # Resumen ejecutivo
│   │
├── Scripts de análisis
│   ├── reporte_completitud_v2.py    # Análisis de completitud
│   ├── validate_excel_planilla.py   # Validación vs Excel
│   ├── recalcular_ratios.py         # Recálculo de ratios
│   └── exportar_csv_actualizados.py # Exportación de CSV
│   │
├── Scripts del pipeline
│   ├── xbrl_parser.py               # Parseo de XBRL
│   ├── pipeline.py                  # Normalización y warehouse
│   ├── ratios.py                    # Cálculo de ratios
│   ├── bank_pipeline.py             # Pipeline bancario
│   └── afp_pipeline.py              # Pipeline de AFPs
│   │
├── Datos
│   ├── output/
│   │   ├── warehouse.db             # Base de datos principal (MASTER DATA)
│   │   ├── normalized_financials.csv
│   │   ├── ratios.csv
│   │   └── ...
│   │
└── Configuración
    ├── tickers_chile.json           # Lista de tickers
    ├── requirements.txt             # Dependencias Python
    └── PlanillaCursoDividendos.xlsx # Excel de validación
```

---

## 🎯 Estados del Proyecto

| Fecha | Versión | Estado | Descripción |
|-------|---------|--------|-------------|
| 2026-04-05 | v4.1 | ✅ Validado | Validación completa vs Excel. 46/47 tickers con 100% completitud |
| 2026-04-02 | v4.0 | ✅ Beta | Pipeline inicial con XBRL + API CMF |
| 2026-03-xx | v3.0 | 🚧 Alpha | Soporte básico de XBRL |

---

## 📊 Métricas Actuales

**Cobertura de datos:**
- **47 empresas** chilenas listadas
- **658 registros** financieros (ticker-año-mes)
- **Cobertura temporal**: 2010-2025 (16 años)
- **Completitud**: 46/47 tickers (97.9%) con 100% de años completos

**Calidad de datos:**
- **96.5%** de datos verificados como confiables
- **3 empresas** corregidas desde Excel manual
- **0 discrepancias críticas** restantes

**Ratios calculados:**
- **4,956 ratios** financieros
- **10 categorías** de ratios (profitability, liquidity, leverage, etc.)
- **Trazabilidad completa** con componentes y quality flags

---

## 🔍 Flujos de Trabajo Comunes

### Análisis de un ticker
```bash
# Consultar historial completo
python query.py --ticker FALABELLA.SN --section all

# Exportar a Excel
python query.py --ticker FALABELLA.SN --format excel
```

### Actualización anual
```bash
# 1. Descargar XBRLs del nuevo año
python -m scraper.main --year 2026 --tickers-only

# 2. Parsear XBRLs
python xbrl_parser.py

# 3. Reconstruir warehouse
python pipeline.py

# 4. Actualizar bancos desde API CMF
python bank_pipeline.py

# 5. Recalcular ratios
python recalcular_ratios.py

# 6. Validar datos
python validate_excel_planilla.py
```

### Análisis de completitud
```bash
# Generar tabla de completitud
python reporte_completitud_v2.py
```

---

## ⚠️ Limitaciones Conocidas

1. **CHILE.SN** - 8/16 años completos (2018-2025 solo balance básico)
2. **CENCOSUD.SN / MALLPLAZA.SN** - Sin flujo de caja (no estaba en Excel)
3. **BICE.SN** - Sin métricas bancarias específicas (loans, deposits)
4. **Pandas** - No compatible con Windows Defender Application Control

Ver [README.md - Limitaciones](README.md#limitaciones-conocidas) para más detalles.

---

## 📞 Soporte

- **Documentación técnica**: [architecture.md](architecture.md)
- **Guía de archivos**: [GUIA_ARCHIVOS.md](GUIA_ARCHIVOS.md)
- **Validación de datos**: [VALIDACION.md](VALIDACION.md)
- **Completitud**: [TABLA_COMPLETITUD.md](TABLA_COMPLETITUD.md)

---

**Última actualización**: 2026-04-05
**Versión**: v4.1 (Validado y listo para producción)
