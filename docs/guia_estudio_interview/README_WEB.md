# Guia sencilla de la web y dashboards

Esta guia explica que aparece en las pantallas del proyecto y que hace cada cosa.

Hay dos experiencias visuales:

1. **Dashboard Streamlit** en `app.py`.
2. **Demo web Next.js** en `aml-interview-demo/`.

Las dos sirven para explicar el proyecto, pero no son exactamente lo mismo.

## Diferencia entre Streamlit y la demo Next.js

### Streamlit

Es el dashboard conectado directamente al pipeline Python.

Usa los CSV generados por:

- `src/ingest_data.py`
- `src/clean_data.py`
- `src/generate_features.py`
- `src/detect_alerts.py`
- `src/credit_risk_metrics.py`

Sirve para ver:

- KPIs reales del dataset sintetico,
- alertas AML,
- tablas de revision,
- calidad de datos,
- capa de riesgo de credito.

### Demo web Next.js

Es una demo visual para entrevista.

Esta en:

- `aml-interview-demo/`

Sirve para contar el proyecto de forma mas interactiva:

- pipeline replay,
- laboratorio de alertas,
- grafo de cuentas,
- scoring simulado,
- SQL evidence,
- credit risk layer,
- interview mode,
- data provenance.

Importante:

> La demo Next.js es una representacion visual para entrevista. No sustituye el pipeline Python principal.

## Como abrir el dashboard Streamlit

Desde la raiz del repo:

```bash
streamlit run app.py
```

Normalmente se abre en:

```text
http://localhost:8501
```

## Pantalla Streamlit: cabecera principal

Titulo:

```text
Risk Reporting & BI Demo
```

Que explica:

- Es una demo educativa.
- Usa datos sinteticos.
- No es un sistema bancario real.
- Convierte datos en KPIs, alertas y visualizaciones.

En la tarjeta lateral se ve el flujo:

- Raw CSV
- Data quality
- Rules
- KPIs
- Review

Tambien aparecen resumenes como:

- numero de transacciones limpias,
- numero de alertas,
- issues de calidad de datos.

## Streamlit seccion 01: Interactive Reporting Workspace

Esta seccion tiene controles para filtrar las alertas AML.

### Filtro Severity

Permite elegir severidad:

- LOW
- MEDIUM
- HIGH

Sirve para ver alertas segun prioridad.

### Filtro Rule / typology

Permite elegir la regla AML:

- SMURFING
- FAN_IN
- FAN_OUT
- HIGH_RISK_GEOGRAPHY

Sirve para analizar una tipologia concreta.

### Focus account

Permite elegir una cuenta especifica.

Si eliges `All accounts`, ves todas.

Si eliges una cuenta, el dashboard se centra en esa cuenta.

### Minimum alert amount

Slider para filtrar alertas por importe minimo.

Sirve para centrarse en alertas con mas impacto economico.

### Detection date range

Filtro de fechas.

Sirve para ver alertas dentro de una ventana temporal.

### Run report refresh

Boton que simula una actualizacion del reporting.

No lanza todo el pipeline real otra vez, pero muestra una animacion de proceso:

- loading cleaned transactions,
- applying alert filters,
- recalculating KPIs,
- rendering review workspace.

Como explicarlo:

> Es una simulacion de refresco BI para entrevista: muestra que el dashboard responde a filtros y recalcula vistas.

## Streamlit seccion 02: KPI Summary

Muestra resumen numerico de AML.

### Total transactions

Numero total de transacciones limpias.

### Filtered alerts

Numero de alertas que quedan con los filtros actuales.

### Filtered alert rate

Proporcion de alertas frente al total de transacciones.

Formula conceptual:

```text
alert_rate = total_alerts / total_transactions
```

### Filtered amount under alert

Importe total asociado a las alertas filtradas.

### Average alert amount

Importe medio por alerta.

### Accounts in current view

Numero de cuentas presentes en la vista filtrada.

### Data quality issues detected

Problemas encontrados en los datos crudos de transacciones.

## Streamlit seccion 03: Risk / Alert Monitoring

Contiene graficos AML.

### Alerts by severity

Grafico de barras con alertas por severidad.

Sirve para responder:

> Cuantas alertas son LOW, MEDIUM o HIGH?

### Alerts by rule / typology

Grafico de barras por regla AML.

Sirve para responder:

> Que tipologia genera mas alertas?

### Alert amount over time

Grafico temporal del importe bajo alerta.

Sirve para ver:

- fechas con mayor importe,
- evolucion temporal,
- concentracion de riesgo.

### Top customers/accounts by alert amount

Ranking de cuentas con mayor importe bajo alerta.

Sirve para priorizar revision.

## Streamlit seccion 04: Alert Review Workspace

Esta parte baja del KPI al detalle.

### Alert to review

Selector de alerta concreta.

Cada opcion combina:

- `alert_id`,
- cuenta,
- regla,
- reason code.

### Tarjetas de detalle

Cuando eliges una alerta, aparecen:

- Account
- Rule
- Severity
- Amount

### Reason code

Explica por que se genero la alerta.

Ejemplo:

```text
Potential structuring pattern
```

### Business explanation

Explicacion mas larga de negocio.

Sirve para defender la alerta ante alguien no tecnico.

### Tabla de transacciones

Muestra transacciones que apoyan la alerta.

Sirve para demostrar evidencia.

Como explicarlo:

> No me quedo en un grafico. Puedo abrir una alerta y ver la evidencia transaccional que la justifica.

### Full filtered alert table

Expander con todas las transacciones/alertas filtradas.

Sirve para revisar el detalle completo.

### Reason code guide

Tabla que relaciona reglas y reason codes.

Sirve como diccionario de explicaciones.

## Streamlit seccion 05: Data Quality

Muestra checks de calidad sobre el CSV raw de transacciones.

### Checks incluidos

- missing key fields,
- duplicated transaction IDs,
- invalid dates,
- zero or negative amounts,
- unexpected categories/statuses.

### Por que importa

Si hay mala calidad de datos:

- las reglas pueden fallar,
- los KPIs pueden estar mal,
- las alertas pueden ser falsas,
- se pierde confianza en el dashboard.

Como explicarlo:

> En riesgo, la calidad de datos es parte del control. No puedo confiar en alertas si el dato de origen esta mal.

## Streamlit seccion 06: Credit Risk Reporting

Esta es la nueva capa educativa de riesgo de credito.

No reemplaza AML.

Anade conceptos de credito encima del proyecto.

### Explicacion inicial

Dice que es una mini capa educativa para entrevista.

Conceptos:

- morosidad 30/60/90,
- NPL >90 DPD,
- PD,
- EAD,
- LGD,
- Expected Loss,
- recovery rate,
- stress simple,
- calidad de datos.

### Stress multiplier

Slider de 1.0 a 2.0.

Sirve para simular deterioro de cartera.

Cuando subes el slider:

- sube la `stressed_pd`,
- sube la `stressed_expected_loss`.

Formula:

```text
stressed_pd = pd * stress_multiplier
```

Con limite:

```text
stressed_pd <= 1
```

### Total loans

Numero de prestamos del dataset.

### NPL rate

Porcentaje de prestamos NPL.

Formula:

```text
npl_rate = npl_count / total_loans
```

### Early warning loans

Prestamos con retraso entre 30 y 90 dias.

Sirve como senal temprana antes de NPL.

### Total EAD

Exposicion total al default.

Formula conceptual:

```text
total_ead = suma de ead
```

### Expected Loss

Perdida esperada total.

Formula:

```text
PD * EAD * LGD
```

### Stressed Expected Loss

Perdida esperada usando la PD estresada.

Sirve para explicar un stress test simple.

### Average Recovery Rate

Promedio de recuperacion observada.

Formula:

```text
recovered_amount / ead
```

### Loans by delinquency bucket

Grafico de barras por bucket:

- CURRENT
- 1-30 DPD
- 31-60 DPD
- 61-90 DPD
- 90+ DPD

Sirve para ver la distribucion de morosidad.

### Expected Loss by product type

Grafico de perdida esperada por producto.

Sirve para responder:

> Que tipo de producto concentra mas perdida esperada?

### Credit risk loan table

Tabla principal de prestamos.

Columnas:

- loan_id,
- customer_id,
- product_type,
- days_past_due,
- delinquency_bucket,
- pd,
- ead,
- lgd,
- expected_loss,
- npl_flag,
- early_warning_flag.

Sirve para ver prestamo por prestamo.

### Stress recalculation detail

Expander con detalle del stress.

Columnas:

- loan_id,
- pd,
- stressed_pd,
- ead,
- lgd,
- expected_loss,
- stressed_expected_loss.

Sirve para ver exactamente como cambia la perdida esperada.

### Credit data quality

Checks de calidad del dataset de prestamos.

Detecta problemas como:

- columnas faltantes,
- campos clave vacios,
- IDs duplicados,
- fechas invalidas,
- exposiciones invalidas,
- PD/LGD fuera de rango,
- recuperacion mayor que EAD.

## Streamlit seccion 07: Interview Mode

Es un guion breve para explicar el proyecto.

Resume:

- que el proyecto carga CSVs,
- limpia datos,
- genera features,
- aplica reglas,
- crea alertas,
- muestra KPIs,
- permite revisar evidencia,
- anade capa de credito.

Sirve para practicar una explicacion de entrevista.

## Como abrir la demo Next.js

Desde la raiz:

```bash
cd aml-interview-demo
npm run dev -- -p 3107
```

Normalmente se abre en:

```text
http://localhost:3107
```

## Demo Next.js: cabecera principal

Titulo:

```text
AMLGuardian Interview Ops Console
```

La cabecera explica que es una consola demo para entrevista.

Muestra metricas rapidas:

- cuentas,
- transacciones,
- alertas,
- SAR candidatas.

Tambien tiene botones:

- Launch Investigation Demo,
- Data Provenance,
- Credit Risk Layer.

## Demo Next.js seccion 01: Pipeline Replay

Simula el pipeline paso a paso.

Sirve para explicar:

- entrada,
- transformacion,
- salida,
- por que importa cada paso.

Botones principales:

- avanzar paso,
- reproducir automaticamente,
- reiniciar.

Como defenderlo:

> Esta seccion ayuda a contar el flujo end-to-end sin abrir codigo.

## Demo Next.js seccion 02: Alert Lab

Permite explorar tipologias AML.

Tipologias visibles:

- Smurfing,
- Fan-in,
- Fan-out,
- Circular flows,
- Layering,
- High-risk geography.

Importante:

> Algunas tipologias aparecen en la demo web como simulacion visual o concepto ampliado. El pipeline principal simplificado se centra en reglas AML basicas.

Que muestra:

- narrativa de la tipologia,
- alertas relacionadas,
- evidencia en tabla,
- transacciones asociadas.

## Demo Next.js seccion 03: Interactive Network Investigation

Muestra un grafo de cuentas y transferencias.

Permite:

- seleccionar cuenta,
- ver vecinos de primer nivel,
- ver vecinos de segundo nivel,
- resaltar ciclos,
- resaltar rutas sospechosas.

Panel lateral:

- cuenta seleccionada,
- risk score,
- risk tier,
- alertas activas,
- PageRank,
- comunidad,
- top features,
- transacciones recientes.

Importante:

> Esta parte es visual y educativa. El grafo ayuda a explicar conexiones entre cuentas, pero no forma parte del flujo Python simplificado principal.

## Demo Next.js seccion 04: Risk Scoring & Explainability

Muestra un score dinamico simulado.

Permite seleccionar una cuenta y activar/desactivar senales.

Ejemplos de senales:

- actividad nocturna,
- muchas contrapartes,
- exposicion geografica,
- patrones de red.

Elementos visibles:

- gauge de score,
- delta contra score base,
- contribuciones tipo SHAP-like,
- comparacion radar entre cuentas.

Importante:

> Es una simulacion para entrevista, no un modelo ML productivo.

## Demo Next.js seccion 05: Credit Risk Interview Layer

Esta es la tarjeta nueva de riesgo de credito.

Explica de forma estatica:

- NPL +90 DPD,
- PD / EAD / LGD,
- Expected Loss,
- Recovery Rate,
- Stress multiplier.

Tambien muestra reglas simples:

- NPL rule: `days_past_due > 90`
- Early warning: `30 <= DPD <= 90`
- Base EL: `PD x EAD x LGD`
- Stress: `PD x multiplier, capped at 1`

Como explicarlo:

> Esta seccion resume la capa de credito que vive en Python/Streamlit. No crea otro motor, solo ayuda a defender conceptos en entrevista.

## Demo Next.js seccion 06: SQL / Evidence View

Muestra una consola de evidencia SQL simulada sobre datos locales.

Partes:

- Query Library,
- boton Run query,
- SQL mostrado,
- tabla de resultados.

Sirve para explicar:

> El analista puede consultar evidencia y no depender solo de una metrica agregada.

## Demo Next.js seccion 07: Interview Mode

Modo guiado de entrevista.

Tiene:

- pasos,
- notas,
- boton Previous,
- boton Next,
- roadmap visual.

Sirve para practicar un discurso de 3 a 5 minutos.

Pasos principales:

1. Entrada y alcance.
2. Transformaciones.
3. Deteccion de tipologias.
4. Valor de red.
5. Score y explicabilidad.
6. Capa de credito.
7. Cierre investigable.

## Demo Next.js seccion 08: Data Provenance

Explica de donde viene el dato.

Tarjetas:

- Raw,
- Normalized,
- Features,
- Alerts,
- Score.

Tambien separa:

- lo que refleja el repo,
- lo que esta simulado en la demo.

Esta seccion es importante porque evita que la demo parezca magia.

Como explicarlo:

> Cada visualizacion debe poder conectarse con una fuente o una transformacion. Eso es trazabilidad.

## Que cosas son reales y que cosas son simuladas

### Mas conectado al pipeline real

- Streamlit.
- CSV de `data/raw/`.
- CSV de `data/processed/`.
- Alertas de `outputs/alerts_sample.csv`.
- Calculos de `src/reporting.py`.
- Calculos de `src/credit_risk_metrics.py`.

### Mas orientado a demo visual

- Grafo interactivo de la web.
- Score dinamico web.
- Contribuciones SHAP-like.
- SQL runner local de la demo web.
- Algunas tipologias ampliadas de la demo web.

Esto no es malo. Es una decision de diseno:

> Streamlit demuestra el pipeline Python. Next.js ayuda a contar la historia visualmente en entrevista.

## Ruta recomendada para ensenar el proyecto

Si tienes poco tiempo:

1. Abre Streamlit.
2. Muestra KPIs AML.
3. Filtra por una regla.
4. Abre una alerta concreta.
5. Ensena reason code y evidencia.
6. Baja a Data Quality.
7. Ensena Credit Risk Reporting.
8. Cambia el stress multiplier.
9. Explica Expected Loss.

Si tienes mas tiempo:

1. Abre la demo Next.js.
2. Lanza Pipeline Replay.
3. Muestra Alert Lab.
4. Muestra grafo.
5. Muestra Credit Risk Layer.
6. Cierra con Interview Mode y Data Provenance.

## Explicacion muy corta de cada web

### Streamlit

> Es el dashboard conectado al pipeline Python. Me permite ver KPIs, alertas, evidencia, calidad de datos y metricas de credito calculadas desde CSV.

### Next.js

> Es una demo visual para entrevista. Me permite contar el proyecto paso a paso con interacciones, grafo, SQL simulado, scoring simulado y una tarjeta de riesgo de credito.

## Frase final para entrevista

> La web no es solo decoracion: esta pensada para contar la trazabilidad completa. Puedo ir desde datos raw hasta features, alertas, reason codes, evidencia, KPIs, calidad de datos y una extension de riesgo de credito con NPL, Expected Loss y stress simple.

