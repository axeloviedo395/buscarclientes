"""
Módulo 2 - Enriquecimiento
---------------------------
Para cada negocio con estado='nuevo':
  - Si tiene web: la visita y revisa SSL, si carga, velocidad, si es
    responsive, si tiene formulario de contacto, si tiene SEO básico,
    y trata de encontrar email / Instagram / Facebook en el HTML.
  - Si no tiene web: no hay nada que analizar, pasa directo.
  - En ambos casos: genera el link de WhatsApp a partir del teléfono.

Al terminar, cambia estado a 'enriquecido' para que el Módulo 3
(scoring) sepa que ya puede procesarlo.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

TIMEOUT_SEG = 10
PAUSA_ENTRE_SITIOS_SEG = 1.0

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Emails "basura" que suelen aparecer en templates y no sirven para contactar
EMAILS_IGNORAR = {"tuemail@ejemplo.com", "email@example.com", "info@example.com"}


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def generar_whatsapp(telefono: str | None) -> str | None:
    """Genera un link wa.me a partir del teléfono de Google.
    Nota: los números argentinos tienen particularidades (el 9 de celular),
    así que esto es una aproximación razonable, no 100% infalible — conviene
    revisar a mano los que vayas a contactar."""
    if not telefono:
        return None
    solo_digitos = re.sub(r"\D", "", telefono)
    if not solo_digitos:
        return None
    if not solo_digitos.startswith("54"):
        solo_digitos = "54" + solo_digitos.lstrip("0")
    return f"https://wa.me/{solo_digitos}"


def analizar_sitio(url: str) -> dict:
    resultado = {
        "tiene_ssl": url.startswith("https://"),
        "sitio_funciona": False,
        "tiempo_carga_ms": None,
        "es_responsive": False,
        "tiene_formulario_contacto": False,
        "tiene_seo_basico": False,
        "email": None,
        "instagram": None,
        "facebook": None,
        "senales_negativas": [],
    }

    try:
        inicio = time.time()
        resp = requests.get(
            url, timeout=TIMEOUT_SEG,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AnalisisWebBot/1.0)"},
        )
        tiempo_ms = int((time.time() - inicio) * 1000)
        resultado["tiempo_carga_ms"] = tiempo_ms
        resultado["sitio_funciona"] = resp.status_code == 200

        if not resultado["sitio_funciona"]:
            resultado["senales_negativas"].append("sitio_no_responde_bien")
            return resultado

        if tiempo_ms > 3000:
            resultado["senales_negativas"].append("carga_lenta")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Responsive: ¿tiene meta viewport?
        viewport = soup.find("meta", attrs={"name": "viewport"})
        resultado["es_responsive"] = viewport is not None
        if not resultado["es_responsive"]:
            resultado["senales_negativas"].append("no_responsive")

        # Formulario de contacto
        resultado["tiene_formulario_contacto"] = soup.find("form") is not None
        if not resultado["tiene_formulario_contacto"]:
            resultado["senales_negativas"].append("sin_formulario_contacto")

        # SEO básico: title + meta description + al menos un h1
        tiene_title = bool(soup.title and soup.title.string and soup.title.string.strip())
        meta_desc = soup.find("meta", attrs={"name": "description"})
        tiene_h1 = soup.find("h1") is not None
        resultado["tiene_seo_basico"] = tiene_title and bool(meta_desc) and tiene_h1
        if not resultado["tiene_seo_basico"]:
            resultado["senales_negativas"].append("sin_seo_basico")

        if not resultado["tiene_ssl"]:
            resultado["senales_negativas"].append("sin_ssl")

        # Buscar email (mailto: primero, texto plano después)
        mailto = soup.select_one('a[href^="mailto:"]')
        if mailto:
            resultado["email"] = mailto["href"].replace("mailto:", "").split("?")[0].strip()
        else:
            match = EMAIL_REGEX.search(resp.text)
            if match and match.group(0).lower() not in EMAILS_IGNORAR:
                resultado["email"] = match.group(0)

        # Buscar Instagram / Facebook en los links de la página
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "instagram.com" in href and not resultado["instagram"]:
                resultado["instagram"] = href
            elif "facebook.com" in href and not resultado["facebook"]:
                resultado["facebook"] = href

    except requests.exceptions.SSLError:
        resultado["senales_negativas"].append("certificado_ssl_invalido")
        resultado["tiene_ssl"] = False
    except requests.exceptions.RequestException:
        resultado["senales_negativas"].append("sitio_no_responde")

    return resultado


def ejecutar():
    sb = get_supabase()

    negocios = sb.table("negocios").select("*").eq("estado", "nuevo").execute().data
    if not negocios:
        print("No hay negocios con estado 'nuevo' para enriquecer.")
        return

    print(f"Enriqueciendo {len(negocios)} negocios...\n")

    for negocio in negocios:
        nombre = negocio.get("nombre") or "(sin nombre)"
        cambios = {"whatsapp": generar_whatsapp(negocio.get("telefono"))}

        if negocio.get("url_web"):
            print(f"🌐 Analizando web de: {nombre} → {negocio['url_web']}")
            analisis = analizar_sitio(negocio["url_web"])
            cambios.update({
                "tiene_ssl": analisis["tiene_ssl"],
                "sitio_funciona": analisis["sitio_funciona"],
                "tiempo_carga_ms": analisis["tiempo_carga_ms"],
                "es_responsive": analisis["es_responsive"],
                "tiene_formulario_contacto": analisis["tiene_formulario_contacto"],
                "tiene_seo_basico": analisis["tiene_seo_basico"],
                "senales_negativas": analisis["senales_negativas"],
            })
            if analisis["email"]:
                cambios["email"] = analisis["email"]
            if analisis["instagram"]:
                cambios["instagram"] = analisis["instagram"]
            if analisis["facebook"]:
                cambios["facebook"] = analisis["facebook"]

            time.sleep(PAUSA_ENTRE_SITIOS_SEG)
        else:
            print(f"⛔ Sin web: {nombre} (candidato fuerte)")
            cambios["senales_negativas"] = ["no_tiene_web"]

        cambios["estado"] = "enriquecido"
        sb.table("negocios").update(cambios).eq("id", negocio["id"]).execute()

    print(f"\n✅ Listo. {len(negocios)} negocios enriquecidos.")


if __name__ == "__main__":
    ejecutar()
