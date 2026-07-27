-- ============================================================
-- SCHEMA - Sistema de captación de clientes (Módulo 1)
-- Ejecutar esto una sola vez en Supabase: Project > SQL Editor > New query
-- ============================================================

-- Tabla de configuración: cada fila es una búsqueda que el sistema
-- va a ejecutar sola. Para agregar una ciudad/rubro nuevo, solo
-- agregás una fila acá (no se toca código).
create table if not exists busquedas (
    id              bigserial primary key,
    pais            text not null default 'Argentina',
    provincia       text not null,
    ciudad          text not null,
    barrio          text,                       -- opcional
    rubro           text not null,
    activa          boolean not null default true,
    ultima_ejecucion timestamptz,
    creado_en       timestamptz not null default now()
);

-- Tabla principal de negocios encontrados
create table if not exists negocios (
    id                bigserial primary key,
    place_id          text unique not null,     -- id de Google, evita duplicados
    busqueda_id       bigint references busquedas(id),
    nombre            text,
    direccion         text,
    ciudad            text,
    telefono          text,
    email             text,
    instagram         text,
    facebook          text,
    whatsapp          text,
    categoria         text,
    horarios          jsonb,
    cantidad_resenas  integer,
    calificacion      numeric(2,1),
    url_maps          text,
    url_web           text,
    tiene_web         boolean default false,
    estado            text not null default 'nuevo',  -- nuevo | enriquecido | scored | contactado | respondio | descartado
    puntaje           integer,                  -- lo llena el Módulo 3 (scoring)
    prioridad         text,                     -- lo llena el Módulo 3
    raw_data          jsonb,                    -- respuesta cruda de Google, por si hace falta reprocesar sin pagar de nuevo
    fecha_encontrado  timestamptz not null default now(),
    fecha_actualizado timestamptz not null default now()
);

create index if not exists idx_negocios_estado on negocios(estado);
create index if not exists idx_negocios_ciudad on negocios(ciudad);

-- Ejemplo: así se agrega una búsqueda nueva (sin tocar el script Python)
-- insert into busquedas (provincia, ciudad, barrio, rubro) values
--   ('Buenos Aires', 'Vicente López', null, 'panaderías'),
--   ('Buenos Aires', 'CABA', 'Palermo', 'gimnasios');
