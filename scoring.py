"""
Módulo 3 - Scoring
-------------------
Toma cada negocio con estado='enriquecido' y calcula un puntaje de
0 a 100 según las reglas del negocio (sin web, muchas reseñas, web
vieja/rota, etc.), y lo clasifica en 5 niveles de prioridad.

Guarda el detalle de qué reglas se aplicaron (detalle_puntaje) para
que después el Módulo 4 (IA) pueda usarlo al escribir el email,
sin tener que volver a analizar nada.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def calcular_puntaje(negocio: dict) -> tuple[int, list[dict]]:
    puntos = 0
    detalle: list[dict] = []

    def sumar(motivo: str, valor: int):
        nonlocal puntos
        puntos += valor
        detalle.append({"motivo": motivo, "puntos": valor})

    # --- Presencia web ---
    if not negocio.get("tiene_web"):
        sumar("No tiene página web", 40)
    else:
        señales_buenas = sum([
            bool(negocio.get("es_responsive")),
            bool(negocio.get("tiene_ssl")),
            bool(negocio.get("tiene_seo_basico")),
            bool(negocio.get("tiene_formulario_contacto")),
            bool(negocio.get("sitio_funciona")),
        ])

        if señales_buenas >= 4:
            sumar("Ya tiene una web moderna y funcional", -30)
        elif señales_buenas <= 1:
            sumar("Tiene web pero con problemas graves (vieja o rota)", 20)

        if not negocio.get("sitio_funciona"):
            sumar("El sitio no responde o funciona mal", 15)
        if not negocio.get("tiene_ssl"):
            sumar("No tiene certificado SSL", 10)
        if (negocio.get("tiempo_carga_ms") or 0) > 3000:
            sumar("La web carga muy lento", 10)
        if not negocio.get("es_responsive"):
            sumar("No es responsive (no se adapta a celular)", 10)
        if not negocio.get("tiene_formulario_contacto"):
            sumar("No tiene formulario de contacto", 5)
        if not negocio.get("tiene_seo_basico"):
            sumar("No tiene SEO básico", 5)

    # --- Reputación / actividad ---
    resenas = negocio.get("cantidad_resenas") or 0
    if resenas > 300:
        sumar(f"Tiene {resenas} reseñas en Google", 20)
    elif resenas > 100:
        sumar(f"Tiene {resenas} reseñas en Google", 12)
    elif resenas > 20:
        sumar(f"Tiene {resenas} reseñas en Google", 6)

    calificacion = negocio.get("calificacion") or 0
    if resenas > 5 and calificacion >= 3.5:
        sumar("El negocio parece activo (buena calificación y reseñas)", 15)

    # --- Canales de contacto detectados ---
    if negocio.get("whatsapp"):
        sumar("Tiene WhatsApp detectado", 10)
    if negocio.get("instagram"):
        sumar("Tiene Instagram vinculado", 8)
    if negocio.get("facebook"):
        sumar("Tiene Facebook vinculado", 5)

    puntos = max(0, min(100, puntos))
    return puntos, detalle


def clasificar_prioridad(puntos: int) -> str:
    if puntos >= 80:
        return "⭐⭐⭐⭐⭐ Muy Alta"
    if puntos >= 60:
        return "⭐⭐⭐⭐ Alta"
    if puntos >= 40:
        return "⭐⭐⭐ Media"
    if puntos >= 20:
        return "⭐⭐ Baja"
    return "⭐ Muy Baja"


def ejecutar():
    sb = get_supabase()

    negocios = sb.table("negocios").select("*").eq("estado", "enriquecido").execute().data
    if not negocios:
        print("No hay negocios con estado 'enriquecido' para puntuar.")
        return

    print(f"Puntuando {len(negocios)} negocios...\n")
    conteo_prioridad = {}

    for negocio in negocios:
        puntos, detalle = calcular_puntaje(negocio)
        prioridad = clasificar_prioridad(puntos)
        conteo_prioridad[prioridad] = conteo_prioridad.get(prioridad, 0) + 1

        sb.table("negocios").update({
            "puntaje": puntos,
            "prioridad": prioridad,
            "detalle_puntaje": detalle,
            "estado": "scored",
        }).eq("id", negocio["id"]).execute()

        print(f"  {negocio.get('nombre', '(sin nombre)'):40s} → {puntos:3d} pts  {prioridad}")

    print("\n✅ Listo. Resumen:")
    for prioridad, cantidad in sorted(conteo_prioridad.items(), reverse=True):
        print(f"  {prioridad}: {cantidad}")


if __name__ == "__main__":
    ejecutar()
