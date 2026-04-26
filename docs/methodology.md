# Metodologia

Este proyecto usa datos sinteticos para practicar un flujo sencillo de analitica AML. No es un sistema de cumplimiento real y no toma decisiones regulatorias.

## 1. Ingestion

Los ficheros `data/raw/accounts.csv` y `data/raw/transactions.csv` se cargan con Pandas desde `src/ingest_data.py`. El objetivo es mantener una entrada clara y facil de revisar:

- cuentas
- transacciones
- importes
- divisas
- paises
- tipo de cuenta

## 2. Limpieza

`src/clean_data.py` aplica transformaciones basicas:

- estandarizacion de nombres de columnas
- conversion de fechas
- normalizacion de divisas
- conversion de importes a euros
- eliminacion de duplicados
- tratamiento de valores nulos sencillos

## 3. Generacion de Features

`src/generate_features.py` crea variables utiles para un analista junior:

- numero de transacciones
- total recibido
- total enviado
- numero de contrapartes unicas
- numero de paises relacionados
- importe medio por transaccion
- indicador de jurisdiccion de mayor riesgo segun una lista de entrenamiento

Estas features no son una evaluacion final del cliente. Sirven para explicar patrones y preparar una tabla para analisis o dashboarding.

## 4. Reglas de Alertas

`src/detect_alerts.py` aplica reglas simples y explicables:

- smurfing / structuring
- fan-in
- fan-out
- geografia de mayor riesgo

Cada alerta incluye una razon y metricas de soporte. El lenguaje es intencionalmente prudente: una alerta puede indicar un patron inusual, pero requiere revision humana y mas contexto.

## 5. Salida Analitica

La salida principal es `outputs/alerts_sample.csv`. Puede usarse para:

- practicar SQL
- construir un dashboard sencillo
- preparar historias de investigacion para entrevista
- explicar como se priorizan patrones para revision

## Limitaciones

- Los datos son sinteticos y pequenos.
- Las reglas tienen umbrales fijos.
- No hay KYC real, investigacion documental ni feedback de analistas.
- La lista de paises es solo una lista de entrenamiento.
- El proyecto no genera decisiones de cumplimiento.
