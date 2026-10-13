# Cambios del generador de informes TGI

Registro de lo que se modificó, por qué y en qué commit. Lo más reciente
arriba. Los detalles técnicos de cada regla viven en `AGENTS.md`.

## 2026-10-13

- **CIPS sin Instant OFF (logger en "Always ON") — `0238448`.** Tausa: el
  rectificador no se interrumpió. Un archivo exporta una sola columna `Voltage`
  (el ON) y el otro `Off Voltage` = 0 en todas las filas; el informe salía con
  abscisas y sin potenciales. Ahora `Voltage` se lee como ON, un OFF de
  exactamente 0 se trata como no medido, la fecha sale de `Time` si no hay
  `On Time`, y la app avisa en la pestaña CIPS y en Generar que el survey no
  trae Instant OFF (no se puede evaluar el criterio de -850 mV; hay que repetir
  con interrupción). El OFF no se recupera de esos archivos.
- **Filas ocultas de las plantillas — `cae797e`.** DCVG trae ocultas las filas
  78-82 (conclusiones) y 88-97 (recomendaciones), PAP la 90. Un DCVG con 10
  conclusiones perdía la 9 y la 10 sin aviso. Toda fila con párrafo se hace
  visible y al abrir filas el estado oculto y los saltos de página se mueven
  con la fila. Los bloques se buscan en toda la hoja (ya no hasta la fila 140).

## 2026-10-09

- **Conclusiones y recomendaciones sin tope — `641c80f`.** La plantilla deja
  pocas filas (CIPS 8 / 2) y lo que no cabía quedaba fuera del informe con el
  aviso "N no cupieron". Ahora se abren filas: recomendaciones y firmas bajan,
  las filas nuevas copian el formato, y los párrafos largos ajustan el alto.
- **Pestaña Conclusiones rota — `3e61ccb`.** Con tipo de ducto "Ramal" y
  tramo "Tausa" (sin el "Ramal" al frente) la pestaña caía con `NameError`:
  una variable mal escrita en `_linea`. Ahora une tipo y tramo ("Ramal Tausa").
- **Traza de Ramal Tausa — `e0ae72a`.** `R_TAU.shp` traía Tausa (D3) y
  Tauramena (D4) juntas, a 130 km: Tausa salía "sin shapefile" y Tauramena con
  un salto falso. Se separaron en `R_TAUS.shp` (3,1 km) y `R_TAU.shp` (4,5 km).
  Al compilar el escritorio hay que borrar `shapefiles.zip` para que entre.
- **Data cruda en `.xls` — `b42395b`.** El logger exporta Excel 97-2003 y el
  cargador solo aceptaba `.xlsx`. Los cargadores de CIPS y del logger DCVG
  aceptan `.xls` y lo convierten a `.xlsx` al subir (`xls_compat.py`, `xlrd`).

## 2026-10-08

- **Eje Y de la gráfica DCVG — `962cc10`.** Fijo de 0 a 100 % (la plantilla
  traía 0..100 y con la severidad en fracción el eje llegaba al 10000 %).
- **Firmas — `7edceec`.** REVISÓ pasa a Javier Jara, Ingeniero Residente.
  APROBÓ sigue Alejandro Rivera, Ingeniero Especialista CP4. ELABORÓ se elige
  en Generar (Pablo Rivera · Edwin López · Juan Gallego).
- **Sin gráficas cada 5 km en DCVG — `dbf63b9`.** El informe solo lleva la
  gráfica general de defectos y la de resistividades.
- **Ciclo de interrupción — `d4821c5`.** PAP y CIPS siempre "ON 1,6 s / OFF
  0,4 s"; DCVG queda vacío y marcado como pendiente de definir. El ciclo en ms
  del Excel de equipos ya no se escribe.
- **OT 2026 — `94d46f3`.** El control de OT de TGI (`consolidado_ot_2026.csv`,
  exportado con `cargar_consolidado_ot.py`) manda sobre el consolidado 2025.
  Solo tramo/tipo/OT/distrito/trimestre: el Excel con valores no se sube.
- **Carga DCVG blindada — `21f09d3`.** Tramo, fecha y recubrimiento se aplican
  aunque falle un paso secundario (logger, equipos, resistividades); lo que
  falla se lista en el mensaje (Marsella quedaba con campos en blanco).
- **Recubrimiento — `225527a`.** FBE confirmado en 38 ramales de
  Mariquita-Cali; Obando sigue pendiente.
- **Firmas en la web — `bd45cb3`.** Revisó/aprobó fijos y selector de quién
  elaboró; sin elegirlo no se puede generar.
- **KMZ solo puntos — `0c4eae5`, `ee0edcd`.** Se quitaron las líneas rectas
  entre postes (y la traza GPS del CIPS): confundían al revisor.

## 2026-10-07

- **Columnas de postes y firmas por etiqueta — `8a18c7d`.** Las columnas de
  'Potenciales PAP' se ubican por encabezado (en CIPS salían corridas), las
  firmas se escriben en el bloque real de cada plantilla (antes salían las de
  ejemplo) y queda una sola `fill_aislamientos`.
- **Hallazgos — `1868246`.** El primer hallazgo va justo debajo del encabezado
  (antes seis filas vacías).
- **FastField DCVG de campo — `5faecc8`.** PK en km con punto ('3.000'),
  filas en blanco descartadas, y la foto del técnico ya no sale como inspector.
- **Gráfica DCVG vs. observaciones — `9fed893`.** Los postes sin pulso no
  anclan el P/RE: la gráfica y las observaciones cuentan lo mismo.
- **Aviso de inspección visual DCVG — `cca12cf`.** Interfases, derivaciones y
  citygates del recorrido se listan para redactar su inspección visual.
- **Norma TM0497 — `46b100d`.** Unificada a AMPP TM0497-2022, sin duplicar.
- **ANTECEDENTES y HUELLA ocultas; gráfica de resistividad — `0dcf696`.**
- **Pestañas retiradas — `82e90e5`.** Bandeja de cargas pendientes, Insp.
  especiales y Aislamientos.
- **KMZ de CIPS — `98537bd`.** Como el de PAP (postes + hallazgos), no 100.000 puntos.
- **Recubrimiento 'En validación' — `cac5329`.** Ya no sale en el informe.
- **Longitud y rango de gráficas del recorrido real — `c5c1887`.**
- **Conclusiones base por tipo — `888efcd`.** DCVG y CIPS ya no salen con texto PAP.
- **Contrato y OT — `3dd3b50`.** Contrato fijo 551007370; la OT escrita a mano manda.

## Pendientes abiertos

- Ciclo de interrupción de DCVG (`datos_tramo.CICLO_DCVG`).
- Recubrimiento de Obando.
- Angel Marin no está en `Listado equipos TGI.xlsx` (serial y calibración salen vacíos).
- El KMZ general no trae la línea de Tausa: afecta las abscisas de un PAP ahí, no al CIPS.
- Tausa CIPS: repetir el registro con el rectificador interrumpido para tener OFF.
- Escritorio: borrar `shapefiles.zip` antes de compilar; las firmas siguen a mano.
