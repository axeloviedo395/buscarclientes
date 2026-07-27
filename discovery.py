"""
Módulo 1 - Descubrimiento de negocios
--------------------------------------
Lee las búsquedas activas desde Supabase (tabla `busquedas`),
consulta la Places API (New) de Google con un field mask acotado
(para pagar lo mínimo posible) y guarda/actualiza los resultados
en la tabla `negocios`.

Diseñado para bajo volumen (free tier / crédito gratis de Google):
- 1 sola llamada a la API por búsqueda (hasta 20 resultados c/u).
- No pide campos "Atmosphere" de más ni fotos.
- Espera 1 segundo entre llamadas para no golpear el rate limit.
"""

import os
import time
import requests
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.environ["GOOGLE_PLACES_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

# Campos pedidos a propósito acotados: nos da lo que pide el usuario
# (nombre, dirección, teléfono, web, rating, reseñas, horarios, maps url)
# sin pedir fotos ni reviews textuales, que son más caras.
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.regularOpeningHours",
    "places.googleMapsUri",
    "places.primaryTypeDisplayName",
    "places.businessStatus",
])

MAX_RESULTS_PER_BUSQUEDA = 20  # tope de la API por consulta de texto
PAUSA_ENTRE_LLAMADAS_SEG = 1.0


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def construir_query_text(busqueda: dict) -> str:
    """Arma el texto de búsqueda a partir de los campos de la fila."""
    partes_lugar = [p for p in [busqueda.get("barrio"), busqueda.get("ciudad")] if p]
    lugar = ", ".join(partes_lugar)
    return f"{busqueda['rubro']} en {lugar}, {busqueda['provincia']}, {busqueda['pais']}"


def buscar_en_google(query_text: str) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": query_text,
        "languageCode": "es",
        "maxResultCount": MAX_RESULTS_PER_BUSQUEDA,
    }
    resp = requests.post(PLACES_ENDPOINT, headers=headers, json=body, timeout=20)
    resp.raise_for_status()
    return resp.json().get("places", [])


def mapear_negocio(place: dict, busqueda_id: int, ciudad: str) -> dict:
    website = place.get("websiteUri")
    return {
        "place_id": place["id"],
        "busqueda_id": busqueda_id,
        "nombre": place.get("displayName", {}).get("text"),
        "direccion": place.get("formattedAddress"),
        "ciudad": ciudad,
        "telefono": place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
        "categoria": place.get("primaryTypeDisplayName", {}).get("text")
                     if isinstance(place.get("primaryTypeDisplayName"), dict) else None,
        "horarios": place.get("regularOpeningHours"),
        "cantidad_resenas": place.get("userRatingCount"),
        "calificacion": place.get("rating"),
        "url_maps": place.get("googleMapsUri"),
        "url_web": website,
        "tiene_web": bool(website),
        "estado": "nuevo",
        "raw_data": place,
        "fecha_actualizado": datetime.now(timezone.utc).isoformat(),
    }


def ejecutar():
    sb = get_supabase()

    busquedas = sb.table("busquedas").select("*").eq("activa", True).execute().data
    if not busquedas:
        print("No hay búsquedas activas en la tabla `busquedas`. Agregá al menos una fila.")
        return

    total_encontrados = 0
    total_nuevos = 0

    for busqueda in busquedas:
        query_text = construir_query_text(busqueda)
        print(f"\n🔍 Buscando: {query_text}")

        try:
            places = buscar_en_google(query_text)
        except requests.HTTPError as e:
            print(f"  ⚠️  Error consultando Google Places: {e} — {e.response.text[:300]}")
            continue

        print(f"  → {len(places)} resultados de Google")
        total_encontrados += len(places)

        for place in places:
            fila = mapear_negocio(place, busqueda["id"], busqueda["ciudad"])
            existe = sb.table("negocios").select("id").eq("place_id", fila["place_id"]).execute().data

            if existe:
                sb.table("negocios").update(fila).eq("place_id", fila["place_id"]).execute()
            else:
                sb.table("negocios").insert(fila).execute()
                total_nuevos += 1

        sb.table("busquedas").update(
            {"ultima_ejecucion": datetime.now(timezone.utc).isoformat()}
        ).eq("id", busqueda["id"]).execute()

        time.sleep(PAUSA_ENTRE_LLAMADAS_SEG)

    print(f"\n✅ Listo. {total_encontrados} negocios procesados, {total_nuevos} nuevos guardados.")


if __name__ == "__main__":
    ejecutar()
