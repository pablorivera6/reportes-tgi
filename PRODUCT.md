# PRODUCT.md — Generador de Reportes TGI (PCC Integrity)

## register
product

## Product Purpose
App interna (Streamlit) que automatiza los informes de inspección de protección
catódica de gasoductos (TGI / OCENSA). Convierte data de campo (FastField API,
Excel de técnicos, data cruda de loggers CIPS) en el informe Excel oficial,
KMZ, paquete de entrega y publicación al portal del cliente.

## Users
- **Ingeniero de integridad PCC** (usuario principal): procesa las inspecciones,
  revisa datos, genera y aprueba informes. Trabaja de día en oficina, con prisa,
  muchas veces con varias inspecciones en cola. No es programador.
- **Técnicos de campo**: NO usan esta app (usan FastField y la app de carga).
- **Cliente TGI**: NO usa esta app (usa el portal de solo lectura).

## Workflow real (el que la UI debe contar)
1. Llega la data: envíos FastField (automático) o cargas de técnicos (app upload).
2. El ingeniero la trae a la app (un clic) y verifica lo cargado.
3. Completa datos generales, revisa pestañas (potenciales, hallazgos...).
4. Genera informe + KMZ + paquete; publica al portal para aprobación.

Tipos de inspección: PAP, CIPS, DCVG. Cada tipo usa fuentes distintas:
- PAP: FastField potenciales (+equipos, rectificadores, aislamientos).
- CIPS: data cruda del logger + shapefile del tramo (LRS).
- DCVG: FastField DCVG (postes+defectos+resistividades+hallazgos) o Excel.

## Brand / Tone
- PCC Integrity: rojo corporativo (#C8102E aprox), blanco, gris; logo espiral.
  El header de la app ya es rojo PCC con "fits you_".
- Tono: técnico pero claro, en español; cero jerga innecesaria; el usuario debe
  saber siempre "qué sigue".

## Anti-references
- Paneles interminables de uploaders sueltos sin explicar cuál usar cuándo.
- Jerga de sistema ("submission", "cola", "pipeline") en la UI.
- Mensajes que no dicen el siguiente paso.

## Constraints
- Streamlit puro (sin componentes custom ni CSS pesado): la jerarquía se logra
  con estructura, agrupación, copy y componentes nativos (tabs, expanders,
  containers con borde, columnas, métricas).
- La app también corre en desktop (PyQt) — no romper el motor compartido.
