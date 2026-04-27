# Risk Reporting & BI Demo - guia de entrevista

## 1. Explicacion de 30 segundos

Este proyecto es una demo educativa de reporting de riesgo con datos transaccionales sinteticos. El flujo carga CSVs, limpia datos basicos, aplica reglas simples de alerta y muestra KPIs en un dashboard de Streamlit. Lo hice para practicar como convertir datos operativos en informacion clara para priorizar revision, explicar reason codes y detectar problemas de calidad de dato.

## 2. Explicacion de 2 minutos

La demo parte de dos ficheros CSV ficticios: cuentas y transacciones. Primero hago una ingesta sencilla con Pandas, normalizo nombres de columnas y guardo una version procesada. Despues limpio campos clave como fechas, importes, divisas, cuentas vacias y duplicados. Con el dataset limpio genero features basicas por cuenta, por ejemplo volumen enviado/recibido, numero de transacciones, contrapartes unicas y exposicion a una lista de paises usada solo para entrenamiento.

Sobre esas tablas aplico reglas explicables: posibles pagos fragmentados, entradas desde muchas contrapartes, salidas hacia muchas contrapartes y transacciones con paises de una lista ficticia de mayor riesgo. Cada alerta tiene severidad, reason code, importe bajo alerta, ventana temporal y estado de revision.

La parte BI esta en el dashboard: KPIs principales, alertas por severidad, alertas por tipologia, importe bajo alerta a lo largo del tiempo, cuentas con mayor importe bajo alerta, tabla de revision y resumen de calidad de dato. La idea no es automatizar decisiones, sino enseñar como prepararia informacion clara para un equipo de reporting o riesgo.

## 3. Relacion con Risk Reporting & BI

- **Reporting:** resume transacciones y alertas en indicadores faciles de leer.
- **BI:** convierte tablas CSV en visualizaciones, filtros y una tabla de revision.
- **Riesgo:** prioriza patrones que pueden requerir revision humana.
- **Calidad de dato:** detecta campos clave vacios, duplicados, fechas invalidas e importes no validos.
- **Comunicacion con negocio:** usa reason codes entendibles, no solo nombres tecnicos de reglas.

## 4. Que NO es este proyecto

- No es un sistema bancario real.
- No es produccion.
- No es un modelo regulatorio.
- No sustituye revision humana.
- No usa datos reales ni informacion sensible.
- Es una demo personal para practicar analisis de datos aplicado a riesgo.

## 5. Guion de demo en entrevista

1. Abrir el dashboard con `streamlit run app.py`.
2. Empezar por **Overview** y aclarar que es una demo academica con datos sinteticos.
3. Enseñar **KPI Summary**: transacciones, alertas, alert rate, importe bajo alerta y calidad de dato.
4. Pasar a **Risk / Alert Monitoring** para explicar severidad, tipologias e importe en el tiempo.
5. Abrir **Alert Review Table** y enseñar una alerta concreta con `transaction_id`, cuenta, importe, regla y reason code.
6. Enseñar **Data Quality** y explicar que los datos raw pueden tener errores antes de limpiar.
7. Cerrar con **Interview Mode**: pipeline, KPIs, valor para BI/riesgo y limitaciones.

## 6. Preguntas tipicas y respuestas

**1. Por que hiciste este proyecto?**  
Lo hice para practicar un caso cercano a Risk Reporting & BI: partir de datos transaccionales, limpiarlos, calcular indicadores y comunicar alertas de forma clara. Queria una demo pequena que pudiera explicar sin venderla como un sistema real.

**2. Como calculas los KPIs?**  
Uso las transacciones limpias y la tabla de alertas. Calculo total de transacciones, total de alertas, alert rate como alertas dividido por transacciones, importe total bajo alerta, importe medio, cuentas unicas y total de incidencias de calidad de dato.

**3. Como limpias los datos?**  
Normalizo nombres de columnas, convierto fechas, paso importes a numerico, normalizo divisas y elimino registros con claves vacias, fechas invalidas, importes no positivos o IDs duplicados.

**4. Que harias si los datos no cuadran?**  
Primero separaria si el problema viene de origen, de transformacion o de logica de reporting. Revisaria conteos entre capas, duplicados, nulos en claves, fechas fuera de rango y reconciliaria totales antes de confiar en el KPI.

**5. Como mejorarias el proyecto?**  
Añadiria mas validaciones, historico de ejecuciones, filtros por periodo, comparativas mensuales y una forma sencilla de marcar alertas revisadas. Tambien documentaria mejor los umbrales y pediria feedback de negocio sobre los reason codes.

**6. Que limitaciones tiene?**  
Los datos son ficticios y pequenos, las reglas tienen umbrales fijos y no hay contexto real de cliente. No hay decisiones automaticas ni validacion regulatoria. Es un prototipo para aprender y explicar el proceso analitico.

**7. Que aprendiste haciendolo?**  
Aprendi que en reporting no basta con crear una alerta: hay que explicar de donde sale, que regla la activa, que importe afecta y si los datos de entrada son fiables. Tambien practique comunicar resultados tecnicos de forma entendible.

**8. Como se relaciona con Risk Reporting & BI?**  
Encaja porque combina pipeline de datos, controles de calidad, KPIs, visualizaciones y una tabla de revision con lenguaje de negocio. Es una version pequena de tareas habituales: preparar datos, medir, detectar excepciones y comunicar resultados.
