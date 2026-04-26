# Case Studies

Los siguientes casos estan escritos como ejemplos de analisis junior. No son conclusiones regulatorias.

## Caso 1: Posible Structuring

**Cuenta:** `ACC-SMURF`  
**Regla:** `SMURFING`  
**Ventana:** 72 horas

La cuenta recibe un ingreso de mayor importe y despues realiza varios pagos inferiores a EUR 9,999 hacia diferentes beneficiarios. Este patron puede indicar fragmentacion de pagos, aunque tambien podria tener una explicacion comercial o personal legitima.

**Metricas a revisar:**

- numero de pagos salientes en 72 horas
- importe total enviado
- numero de beneficiarios distintos
- relacion entre el ingreso inicial y las salidas posteriores

**Siguiente paso analitico:**

El caso se escalaria a un analista para revisar el perfil esperado de la cuenta, la relacion con los beneficiarios y si el comportamiento es habitual para ese cliente.

## Caso 2: Cuenta de Coleccion

**Cuenta:** `ACC-FANIN`  
**Regla:** `FAN_IN`  
**Ventana:** 24 horas

La cuenta recibe fondos desde varias contrapartes distintas en un mismo dia. Este comportamiento puede ser normal en una cuenta de negocio, pero tambien puede indicar que la cuenta esta actuando como punto de concentracion.

**Metricas a revisar:**

- numero de originadores unicos
- importe total recibido
- frecuencia de eventos similares
- tipo de cuenta y actividad esperada

**Siguiente paso analitico:**

La alerta requiere revisar si la actividad encaja con el perfil del cliente. Si no encaja, podria priorizarse para investigacion adicional.

## Caso 3: Exposicion Geografica

**Cuenta:** `ACC-GEO`  
**Regla:** `HIGH_RISK_GEOGRAPHY`

La cuenta tiene transacciones con contrapartes de paises incluidos en una pequena lista de entrenamiento. La alerta no significa que la actividad sea irregular por si sola; solo indica que el pais de la contraparte aumenta la necesidad de contexto.

**Metricas a revisar:**

- paises involucrados
- importe total
- direccion del dinero
- historial previo con esas contrapartes

**Siguiente paso analitico:**

El caso se revisaria junto con informacion del cliente, proposito de la relacion y documentacion disponible.
