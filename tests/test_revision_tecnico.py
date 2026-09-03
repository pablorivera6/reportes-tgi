"""Lo que falta no se arregla en el generador: se le pide al técnico."""
import revision


INSP = {"tramo": "Ansermanuevo", "tipo": "DCVG", "fecha": "2026-03-04",
        "inspector": "Juan Perez", "ot": "OT-9"}


def test_mensaje_nombra_tramo_tipo_y_lo_que_falta():
    obs = [{"categoria": "falta_info", "nota": "faltan las fotos de los defectos"},
           {"categoria": "falta_info", "nota": "falta la resistividad del K12"},
           {"categoria": "texto_campo", "nota": "esto no va en el mensaje"}]
    msg = revision.mensaje_tecnico(INSP, obs)
    assert "Ansermanuevo" in msg and "DCVG" in msg
    assert "faltan las fotos de los defectos" in msg
    assert "falta la resistividad del K12" in msg
    assert "esto no va en el mensaje" not in msg


def test_sin_falta_info_no_hay_mensaje():
    assert revision.mensaje_tecnico(INSP, [{"categoria": "texto_campo",
                                            "nota": "x"}]) == ""
