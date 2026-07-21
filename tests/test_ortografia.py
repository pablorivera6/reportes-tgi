"""Los comentarios de campo llegan con errores de digitación del logger;
el informe no puede salir con errores de ortografía."""
from cips_adapter import _corregir_texto


def test_correcciones_comunes():
    casos = {
        'cruse caño': 'Cruce caño',
        'cruse rio  tramo aerio': 'Cruce río tramo aéreo',
        'fin cruse de rio y tramo aerio': 'Fin cruce de río y tramo aéreo',
        'malla enseramiento': 'Malla encerramiento',
        'paryidura cable': 'Partidura cable',
        'cruse linea de alta tencion': 'Cruce línea de alta tensión',
        'salida valvula pk 0+000': 'Salida válvula PK 0+000',
        'pk 5+000 abcisado': 'PK 5+000 abscisado',
        'salto tramo en montado': 'Salto tramo enmontado',
        'sipaso tramo enmontado salto': 'Sin paso tramo enmontado salto',
    }
    for crudo, esperado in casos.items():
        assert _corregir_texto(crudo) == esperado, (
            f"{crudo!r} -> {_corregir_texto(crudo)!r}, esperaba {esperado!r}")


def test_no_toca_texto_correcto():
    assert _corregir_texto('Cruce de vía principal') == 'Cruce de vía principal'
    assert _corregir_texto('') == ''
