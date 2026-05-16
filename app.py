"""
============================================================
CALCULADORA DE VALOR DE RECONSTRUCCIÓN — SEGUROS CHILE
Conforme DFL 251, DS 1055, CCom art. 553,
Ley 21.442 (Copropiedad) y NCG 556 CMF (dic. 2025)
============================================================
Para ejecutar localmente:
    pip install streamlit pandas
    streamlit run app.py

Para publicar en Streamlit Community Cloud:
    1. Suba este archivo y requirements.txt a GitHub
    2. Vaya a share.streamlit.io y conecte el repo
    3. Seleccione app.py como archivo principal
============================================================
"""

import streamlit as st
import pandas as pd
from datetime import date

# ─────────────────────────────────────────────────────────
# TABLA DE REFERENCIAS DE MERCADO (UF/m²) — 2025-2026
# ─────────────────────────────────────────────────────────
# Fuentes consultadas:
#   · MINVU – Tabla de Costos Unitarios de Construcción (actualización trimestral)
#   · Troncoso Arquitectos – Precio m² construcción Chile 2025
#   · Constructora Márquez Arranz – Costos construcción Gran Concepción 2025
#   · Almazán Ltda. – Costo construcción sur Chile 2025
#   · Mercado privado y corredores de seguros (estimación propia)
#
# IMPORTANTE: Estos rangos son referenciales para orientar al usuario.
# El VUB definitivo debe ser validado por un tasador o corredor habilitado.
# La tabla MINVU oficial está en pesos y se actualiza trimestralmente en:
# https://www.minvu.gob.cl/elementos-tecnicos/tabla-de-costos-unitarios/

REFERENCIAS_VUB = {
    # (zona, tipo_construccion): {"basico": (min,max), "medio": (min,max), "alto": (min,max)}
    # Zona Metropolitana (RM)
    ("Metropolitana", "Casa / Albañilería"):   {"Básico": (18, 22), "Medio": (23, 30), "Alto": (31, 42)},
    ("Metropolitana", "Casa / Metalcon"):       {"Básico": (16, 20), "Medio": (21, 28), "Alto": None},
    ("Metropolitana", "Depto / Hormigón"):      {"Básico": None,     "Medio": (25, 33), "Alto": (34, 48)},
    ("Metropolitana", "Edificio / Hormigón"):   {"Básico": None,     "Medio": (26, 35), "Alto": (36, 52)},
    ("Metropolitana", "Comunidad / Hormigón"):  {"Básico": None,     "Medio": (25, 34), "Alto": (35, 50)},
    # Zona Intermedia (ciudades medianas: Valparaíso, Concepción, Temuco, etc.)
    ("Intermedia", "Casa / Albañilería"):       {"Básico": (17, 21), "Medio": (22, 29), "Alto": (30, 40)},
    ("Intermedia", "Casa / Metalcon"):          {"Básico": (15, 19), "Medio": (20, 27), "Alto": None},
    ("Intermedia", "Depto / Hormigón"):         {"Básico": None,     "Medio": (24, 32), "Alto": (33, 46)},
    ("Intermedia", "Edificio / Hormigón"):      {"Básico": None,     "Medio": (25, 34), "Alto": (35, 50)},
    ("Intermedia", "Comunidad / Hormigón"):     {"Básico": None,     "Medio": (24, 33), "Alto": (34, 48)},
    # Zona Aislada (norte minero, zonas rurales extremas, Aysén, Magallanes)
    ("Aislada", "Casa / Albañilería"):          {"Básico": (20, 26), "Medio": (27, 36), "Alto": (37, 50)},
    ("Aislada", "Casa / Metalcon"):             {"Básico": (18, 23), "Medio": (24, 32), "Alto": None},
    ("Aislada", "Depto / Hormigón"):            {"Básico": None,     "Medio": (29, 38), "Alto": (39, 55)},
    ("Aislada", "Edificio / Hormigón"):         {"Básico": None,     "Medio": (30, 40), "Alto": (41, 58)},
    ("Aislada", "Comunidad / Hormigón"):        {"Básico": None,     "Medio": (29, 39), "Alto": (40, 56)},
}

ZONA_LABEL_CORTA = {
    "Metropolitana (RM y ciudades grandes)": "Metropolitana",
    "Intermedia (ciudades medianas)":        "Intermedia",
    "Aislada (zonas rurales o extremas)":    "Aislada",
}

TIPO_SISTEMA_LABEL = {
    ("Casa",      "Albañilería"): "Casa / Albañilería",
    ("Casa",      "Metalcon"):    "Casa / Metalcon",
    ("Depto",     "Hormigón"):    "Depto / Hormigón",
    ("Edificio",  "Hormigón"):    "Edificio / Hormigón",
    ("Comunidad", "Hormigón"):    "Comunidad / Hormigón",
}

# ─────────────────────────────────────────────────────────
# PARÁMETROS GENERALES
# ─────────────────────────────────────────────────────────
FACTOR_GEOGRAFICO = {
    "Metropolitana (RM y ciudades grandes)": 1.05,
    "Intermedia (ciudades medianas)":        1.00,
    "Aislada (zonas rurales o extremas)":    1.15,
}

SISTEMAS_POR_TIPO = {
    "Casa":      ["Albañilería", "Metalcon"],
    "Depto":     ["Hormigón"],
    "Edificio":  ["Hormigón"],
    "Comunidad": ["Hormigón"],
}

NIVELES_POR_TS = {
    ("Casa",      "Albañilería"): ["Básico", "Medio", "Alto"],
    ("Casa",      "Metalcon"):    ["Básico", "Medio"],
    ("Depto",     "Hormigón"):    ["Medio", "Alto"],
    ("Edificio",  "Hormigón"):    ["Medio", "Alto"],
    ("Comunidad", "Hormigón"):    ["Medio", "Alto"],
}

COSTOS_IND = {
    "Diseño del proyecto":       0.03,
    "Gastos generales de obra":  0.06,
    "Utilidad del contratista":  0.12,
    "Imprevistos":               0.10,
}
TASA_IVA = 0.19


# ─────────────────────────────────────────────────────────
# MOTOR DE CÁLCULO
# ─────────────────────────────────────────────────────────
def factor_normativo(anio):
    if anio < 1985:   return 1.15
    if anio <= 2000:  return 1.10
    if anio <= 2010:  return 1.05
    return 1.00

def factor_altura(pisos):
    if pisos <= 2:   return 1.00
    if pisos <= 5:   return 1.05
    if pisos <= 10:  return 1.10
    return 1.15

def calcular_vr(vub, superficie, zona_label, pisos, anio, aplica_iva):
    fg = FACTOR_GEOGRAFICO[zona_label]
    fn = factor_normativo(anio)
    fa = factor_altura(pisos)
    cd = superficie * vub * fg * fn * fa
    ind_det  = {k: cd * v for k, v in COSTOS_IND.items()}
    costos_i = sum(ind_det.values())
    subtotal = cd + costos_i
    monto_iv = subtotal * TASA_IVA if aplica_iva else 0.0
    vr       = subtotal + monto_iv
    return {"vub": vub, "fg": fg, "fn": fn, "fa": fa,
            "costo_directo": cd, "ind_det": ind_det,
            "costos_ind": costos_i, "subtotal": subtotal,
            "monto_iva": monto_iv, "aplica_iva": aplica_iva, "vr": vr}

def evaluar_poliza(monto, vr):
    if monto <= 0 or vr <= 0: return 0.0, False
    r = monto / vr
    return r, r < 1.0

def indemn_proporcional(danio, monto, vr):
    ratio, infra = evaluar_poliza(monto, vr)
    return danio * ratio if infra else danio


# ─────────────────────────────────────────────────────────
# HELPER: PANEL DE REFERENCIA VUB
# ─────────────────────────────────────────────────────────
def panel_referencia_vub(zona_label, tipo, sistema, nivel):
    """
    Muestra una caja informativa con rangos de mercado para el
    tipo/sistema/nivel/zona seleccionados, y una tabla completa de referencia.
    """
    zona_corta = ZONA_LABEL_CORTA.get(zona_label, "")
    ts_label   = TIPO_SISTEMA_LABEL.get((tipo, sistema), "")
    clave      = (zona_corta, ts_label)
    ref        = REFERENCIAS_VUB.get(clave, {})
    rango      = ref.get(nivel) if ref else None

    with st.expander("📊 Valores de referencia de mercado (UF/m²)", expanded=True):
        st.caption(
            "Rangos referenciales estimados para Chile 2025–2026, basados en datos de mercado "
            "de MINVU, constructoras y corredores de seguros. **No son valores oficiales** — "
            "el VUB definitivo debe ser validado por un tasador o corredor habilitado. "
            "La tabla oficial MINVU (en pesos) se actualiza trimestralmente en "
            "[minvu.gob.cl](https://www.minvu.gob.cl/elementos-tecnicos/tabla-de-costos-unitarios/)."
        )
        if rango:
            st.info(
                f"**Rango referencial para su selección** — "
                f"{tipo} / {sistema} / {nivel} / {zona_corta}: "
                f"**{rango[0]} – {rango[1]} UF/m²**"
            )
        elif ts_label and zona_corta:
            st.warning(
                f"No hay rango de referencia disponible para "
                f"{tipo} / {sistema} / {nivel} / {zona_corta}. "
                f"Ingrese el VUB según tasación propia o corredor."
            )

        # Tabla completa de referencia por zona actual
        filas = []
        for (zc, ts), niveles in REFERENCIAS_VUB.items():
            if zc != zona_corta:
                continue
            for niv, rng in niveles.items():
                if rng:
                    filas.append({
                        "Tipo / Sistema": ts,
                        "Nivel": niv,
                        "Mín (UF/m²)": rng[0],
                        "Máx (UF/m²)": rng[1],
                        "Promedio ref.": round((rng[0] + rng[1]) / 2, 1),
                    })

        if filas:
            st.markdown(f"**Tabla completa — zona {zona_corta}**")
            df = pd.DataFrame(filas).sort_values(["Tipo / Sistema", "Nivel"])
            st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────
# HELPER: FORMULARIO DE UN COMPONENTE CON VUB MANUAL
# ─────────────────────────────────────────────────────────
def ui_comp(prefix, zona, pisos, anio, aplica_iva,
            default_tipo="Comunidad", label_tipo="Tipo de inmueble"):
    tipos = list(SISTEMAS_POR_TIPO.keys())
    idx   = tipos.index(default_tipo) if default_tipo in tipos else 0
    tipo  = st.selectbox(label_tipo, tipos, index=idx, key=f"{prefix}_tipo")
    sis   = st.selectbox("Sistema constructivo",
                         SISTEMAS_POR_TIPO[tipo], key=f"{prefix}_sis")
    niv   = st.selectbox("Nivel de terminaciones",
                         NIVELES_POR_TS[(tipo, sis)], key=f"{prefix}_niv",
                         help="Básico = sin lujos · Medio = estándar · Alto = premium")

    # Panel de referencia VUB
    if zona:
        panel_referencia_vub(zona, tipo, sis, niv)

    # Obtener rango sugerido para el placeholder
    zona_corta = ZONA_LABEL_CORTA.get(zona, "")
    ts_label   = TIPO_SISTEMA_LABEL.get((tipo, sis), "")
    ref        = REFERENCIAS_VUB.get((zona_corta, ts_label), {})
    rango      = ref.get(niv)
    promedio   = round((rango[0] + rango[1]) / 2, 1) if rango else None
    ph_vub     = f"Ref: {rango[0]}–{rango[1]} UF/m² (promedio {promedio})" if rango else "Ej: 28.0"

    vub = st.number_input(
        "VUB — Valor Unitario Base (UF/m²)",
        min_value=1.0, max_value=200.0, value=None,
        step=0.5, format="%.1f",
        placeholder=ph_vub,
        key=f"{prefix}_vub",
        help=(
            "Ingrese el VUB según tasación propia, corredor de seguros o tabla MINVU convertida a UF. "
            "El panel de referencia superior muestra rangos de mercado orientativos."
        ),
    )

    sup = st.number_input(
        "Superficie (m²)", min_value=1, max_value=500_000,
        value=None, placeholder="Ej: 3500", key=f"{prefix}_sup",
    )
    monto = st.number_input(
        "Monto asegurado en póliza (UF)", min_value=0,
        value=None, placeholder="0", key=f"{prefix}_monto",
        help="Ingrese 0 si no hay seguro contratado para este componente.",
    )
    return {"tipo": tipo, "sis": sis, "niv": niv, "vub": vub,
            "sup": sup, "monto": monto,
            "zona": zona, "pisos": pisos, "anio": anio, "aplica_iva": aplica_iva}


def validar_comp(d, campo):
    errs = []
    if not d.get("vub"):  errs.append(f"Ingrese el VUB (UF/m²) de {campo}.")
    if not d.get("sup"):  errs.append(f"Ingrese la superficie de {campo}.")
    if d.get("monto") is None: errs.append(f"Ingrese el monto asegurado de {campo} (puede ser 0).")
    return errs


# ─────────────────────────────────────────────────────────
# HELPER: MOSTRAR RESULTADO DE UN COMPONENTE
# ─────────────────────────────────────────────────────────
def ui_show(label, res, datos, danio_pct, nota="", expanded=True):
    vr    = res["vr"]
    monto = datos.get("monto") or 0
    ratio, infra = evaluar_poliza(monto, vr)
    danio  = vr * (danio_pct / 100)
    indemn = indemn_proporcional(danio, monto, vr)

    with st.expander(f"📦 {label} — **{vr:,.2f} UF**", expanded=expanded):
        if nota:
            st.caption(nota)
        if monto <= 0:
            st.info("ℹ️ Sin monto asegurado registrado para este componente.")
        elif infra:
            st.warning(f"⚠️ **Infrasegurado.** Cobertura: **{ratio*100:.1f}%** — Brecha: **{vr-monto:,.2f} UF**")
        else:
            st.success(f"✅ Cobertura adecuada ({ratio*100:.1f}%)")

        c1, c2, c3 = st.columns(3)
        c1.metric("Valor de reconstrucción", f"{vr:,.2f} UF")
        c2.metric("Monto asegurado", f"{monto:,.2f} UF" if monto > 0 else "No indicado")
        c3.metric("Cobertura", f"{ratio*100:.1f}%" if monto > 0 else "—",
                  delta=f"{(ratio-1)*100:.1f}%" if monto > 0 else None,
                  delta_color="normal" if not infra else "inverse")
        if monto > 0:
            st.progress(min(ratio, 1.0), text=f"Cobertura: {ratio*100:.1f}%")

        st.markdown("**Desglose completo del cálculo**")
        st.markdown(f"""
| # | Concepto | Valor |
|---|----------|-------|
| 1 | VUB ingresado — {datos.get('tipo','')}/{datos.get('sis','')}/{datos.get('niv','')} | **{res['vub']:.1f} UF/m²** |
| 2 | × Factor geográfico ({datos.get('zona','')[:15]}…) | {res['fg']:.2f} |
| 3 | × Factor normativo (año {datos.get('anio','')}) | {res['fn']:.2f} |
| 4 | × Factor altura ({datos.get('pisos','')} pisos) | {res['fa']:.2f} |
| 5 | **Costo directo** ({(datos.get('sup') or 0):,.0f} m²) | **{res['costo_directo']:,.2f} UF** |
| 6a | + Diseño del proyecto (3%) | {res['ind_det']['Diseño del proyecto']:,.2f} UF |
| 6b | + Gastos generales de obra (6%) | {res['ind_det']['Gastos generales de obra']:,.2f} UF |
| 6c | + Utilidad del contratista (12%) | {res['ind_det']['Utilidad del contratista']:,.2f} UF |
| 6d | + Imprevistos (10%) | {res['ind_det']['Imprevistos']:,.2f} UF |
| 7 | **Subtotal sin IVA** | **{res['subtotal']:,.2f} UF** |
| 8 | + IVA 19% | {res['monto_iva']:,.2f} UF |
| ✓ | **VALOR DE RECONSTRUCCIÓN** | **{vr:,.2f} UF** |
""")
        st.markdown(f"**Simulación de siniestro — daño del {danio_pct}%**")
        s1, s2, s3 = st.columns(3)
        s1.metric("Daño estimado", f"{danio:,.2f} UF")
        s2.metric("Indemnización real", f"{indemn:,.2f} UF" if monto > 0 else "—")
        if infra:
            s3.metric("Pérdida no cubierta", f"{danio-indemn:,.2f} UF", delta_color="inverse")
            st.warning(
                f"**Regla proporcional (Art. 553 CCom):** recibiría **{indemn:,.2f} UF** "
                f"en vez de **{danio:,.2f} UF**. Pérdida no cubierta: **{danio-indemn:,.2f} UF**."
            )


# ─────────────────────────────────────────────────────────
# GENERADOR DE INFORME TXT
# ─────────────────────────────────────────────────────────
def _bloque_txt(etiq, res, datos, danio_pct):
    monto = datos.get("monto") or 0
    ratio, infra = evaluar_poliza(monto, res["vr"])
    vr    = res["vr"]
    danio = vr * (danio_pct / 100)
    ind   = indemn_proporcional(danio, monto, vr)
    lns   = [
        f"  [{etiq}]",
        f"    Tipo / Sistema / Nivel  : {datos.get('tipo','')}/{datos.get('sis','')}/{datos.get('niv','')}",
        f"    VUB ingresado           : {res['vub']:.1f} UF/m²",
        f"    Superficie              : {datos.get('sup',0):,.0f} m²",
        f"    Factor geográfico       : {res['fg']:.2f}",
        f"    Factor normativo        : {res['fn']:.2f}  (año {datos.get('anio','')})",
        f"    Factor altura           : {res['fa']:.2f}  ({datos.get('pisos','')} pisos)",
        f"    Costo directo           : {res['costo_directo']:>12,.2f} UF",
        f"    Costos indirectos (31%) : {res['costos_ind']:>12,.2f} UF",
        f"      · Diseño (3%)         : {res['ind_det']['Diseño del proyecto']:>12,.2f} UF",
        f"      · Gastos gral. (6%)   : {res['ind_det']['Gastos generales de obra']:>12,.2f} UF",
        f"      · Utilidad (12%)      : {res['ind_det']['Utilidad del contratista']:>12,.2f} UF",
        f"      · Imprevistos (10%)   : {res['ind_det']['Imprevistos']:>12,.2f} UF",
        f"    Subtotal s/IVA          : {res['subtotal']:>12,.2f} UF",
        (f"    IVA 19%                 : {res['monto_iva']:>12,.2f} UF"
         if res["aplica_iva"] else
         f"    IVA 19%                 :       no aplica"),
        f"    VALOR RECONSTRUCCIÓN    : {vr:>12,.2f} UF",
        "",
        (f"    Monto asegurado         : {monto:>12,.2f} UF"
         if monto > 0 else
         f"    Monto asegurado         :    No indicado"),
        (f"    Cobertura               : {ratio*100:>11.1f} %"
         if monto > 0 else
         f"    Cobertura               :            —"),
        f"    Infraseguro             : {'SÍ ⚠' if infra else 'NO ✓'}",
    ]
    if infra:
        lns.append(f"    Brecha sin cubrir       : {vr-monto:>12,.2f} UF")
    lns += [
        "",
        f"    Simulación daño {danio_pct:.0f}%",
        f"      Daño estimado         : {danio:>12,.2f} UF",
        (f"      Indemnización real    : {ind:>12,.2f} UF"
         if monto > 0 else
         f"      Indemnización real    :    Ver valor de rec."),
    ]
    if infra:
        lns.append(f"      Pérdida no cubierta   : {danio-ind:>12,.2f} UF")
    return "\n".join(lns)


def generar_informe(caso):
    sep  = "=" * 64
    sep2 = "─" * 64
    hoy  = date.today().strftime("%d/%m/%Y")
    lns  = [
        "INFORME DE VALOR DE RECONSTRUCCIÓN",
        "Conforme DFL 251, DS 1055, CCom art. 553 y Ley 21.442",
        sep,
        f"  Nombre / Referencia  : {caso['nombre']}",
        f"  Dirección            : {caso['direccion']}",
        f"  Zona geográfica      : {caso.get('zona','—')}",
        f"  Número de pisos      : {caso.get('pisos','—')}",
        f"  Año de construcción  : {caso.get('anio','—')}",
        f"  Fecha de cálculo     : {hoy}",
        sep, "",
    ]
    modo = caso["modo"]
    if modo == "simple":
        lns.append("INMUEBLE COMPLETO\n")
        c = caso["comp"]
        lns.append(_bloque_txt("Inmueble completo", c["res"], c, caso["danio_pct"]))
    elif modo == "comunes":
        lns.append("BIENES Y ESPACIOS COMUNES  (Ley 21.442 art. 43)\n")
        c = caso["comp"]
        lns.append(_bloque_txt("Bienes comunes", c["res"], c, caso["danio_pct"]))
    elif modo == "comunidad":
        lns.append("PÓLIZA COLECTIVA — NCG 556 CMF\n")
        lns.append("BLOQUE 1: BIENES Y ESPACIOS COMUNES\n")
        c = caso["comp_comun"]
        lns.append(_bloque_txt("Bienes comunes", c["res"], c, caso["danio_pct"]))
        lns += ["", sep2, "", "BLOQUE 2: UNIDADES PRIVADAS\n"]
        for u in caso["unidades"]:
            lns.append(_bloque_txt(u.get("nombre") or "Unidad", u["res"], u, caso["danio_pct"]))
            lns.append("")
        vr_t = caso["total_vr"]
        m_t  = caso["total_monto"]
        r_t, i_t = evaluar_poliza(m_t, vr_t)
        d_t  = vr_t * (caso["danio_pct"] / 100)
        ind_t = indemn_proporcional(d_t, m_t, vr_t)
        lns += [sep2, "CONSOLIDADO TOTAL\n",
                f"  VR bienes comunes            : {caso['vr_comun']:>12,.2f} UF",
                f"  VR unidades privadas         : {caso['vr_units']:>12,.2f} UF",
                f"  VR TOTAL COMUNIDAD           : {vr_t:>12,.2f} UF",
                (f"  Monto asegurado total        : {m_t:>12,.2f} UF"
                 if m_t > 0 else
                 f"  Monto asegurado total        :    No indicado"),
                (f"  Cobertura global             : {r_t*100:>11.1f} %"
                 if m_t > 0 else
                 f"  Cobertura global             :            —"),
                f"  Infraseguro global           : {'SÍ ⚠' if i_t else 'NO ✓'}"]
        if m_t > 0:
            lns += [f"  Daño total simulado ({caso['danio_pct']:.0f}%)    : {d_t:>12,.2f} UF",
                    f"  Indemnización global         : {ind_t:>12,.2f} UF"]
            if i_t:
                lns.append(f"  Pérdida no cubierta          : {d_t-ind_t:>12,.2f} UF")
    lns += ["", sep2,
            "Nota: Informe referencial. Verificar con tasador habilitado y póliza vigente.",
            "Normativa: DFL 251 · DS 1055 · CCom art. 553 · Ley 21.442 · NCG 556 CMF.",
            "VUB: ingresado por el usuario. Para tabla oficial ver minvu.gob.cl"]
    return "\n".join(lns)


# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN PÁGINA
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Seguro de Reconstrucción — Chile",
    page_icon="🏢", layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown("""
<style>
    .stApp { max-width: 820px; margin: auto; }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem; }
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.2rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("🏢 Calculadora de Valor de Reconstrucción")
st.caption("Seguros de inmuebles en Chile · DFL 251 · DS 1055 · CCom art. 553 · Ley 21.442 · NCG 556 CMF")

tab_calc, tab_casos, tab_como = st.tabs(["📐 Calcular", "📋 Mis casos", "ℹ️ Marco normativo"])


# ══════════════════════════════════════════════════════════
# PESTAÑA: CALCULAR
# ══════════════════════════════════════════════════════════
with tab_calc:

    st.subheader("Identificación de la propiedad")
    cn, cd = st.columns(2)
    with cn: nombre    = st.text_input("Nombre o referencia", placeholder="Ej: Edificio Torres del Parque")
    with cd: direccion = st.text_input("Dirección", placeholder="Calle, número, comuna, región")

    st.subheader("Datos generales del inmueble")
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        zona = st.selectbox("Zona geográfica", [""] + list(FACTOR_GEOGRAFICO.keys()),
                            format_func=lambda x: "Seleccionar..." if x == "" else x)
    with g2: pisos      = st.number_input("N° de pisos",   min_value=1, max_value=100, value=None, placeholder="Ej: 12")
    with g3: anio       = st.number_input("Año construc.", min_value=1900, max_value=2025, value=None, placeholder="Ej: 2005")
    with g4: aplica_iva = st.checkbox("IVA (19%)", value=True)

    danio_pct = st.slider("% de daño a simular", 1, 100, 50,
                          help="Porcentaje del inmueble dañado en el siniestro hipotético.")

    datos_ok = bool(zona and pisos and anio)

    st.subheader("¿Qué desea calcular?")
    modo = st.radio("Seleccione el alcance:", [
        "🏠  Inmueble completo — casas, locales o edificio en bloque",
        "🏛️  Solo bienes y espacios comunes — póliza de la comunidad (Ley 21.442 art. 43)",
        "🏢  Comunidad completa — bienes comunes + unidades privadas (NCG 556 CMF)",
    ])
    modo_key = "simple" if "completo" in modo else ("comunes" if "Solo bienes" in modo else "comunidad")
    st.divider()

    # ══════════════════════════════
    # MODO 1: INMUEBLE COMPLETO
    # ══════════════════════════════
    if modo_key == "simple":
        st.markdown("#### Datos del inmueble")
        if not datos_ok:
            st.info("Complete primero zona, pisos y año de construcción.")
            d = None
        else:
            d = ui_comp("s", zona, pisos, anio, aplica_iva, default_tipo="Edificio")

        if st.button("Calcular", type="primary", use_container_width=True, key="btn_s"):
            errs = [] if datos_ok else ["Complete zona, pisos y año."]
            if d: errs += validar_comp(d, "el inmueble")
            for e in errs: st.error(f"⚠️ {e}")
            if not errs:
                res  = calcular_vr(d["vub"], d["sup"], zona, pisos, anio, aplica_iva)
                ui_show("Inmueble completo", res, {**d, "zona": zona, "pisos": pisos, "anio": anio}, danio_pct)
                caso = dict(nombre=nombre or "Sin nombre", direccion=direccion or "—",
                            zona=zona, pisos=pisos, anio=anio, danio_pct=danio_pct,
                            modo="simple",
                            comp={**d, "res": res, "zona": zona, "pisos": pisos, "anio": anio},
                            total_vr=res["vr"], total_monto=d["monto"] or 0)
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("💾 Guardar", use_container_width=True, key="g_s"):
                        st.session_state.setdefault("casos", []).append(caso)
                        st.success("Caso guardado.")
                with b2:
                    st.download_button("📄 Descargar informe", data=generar_informe(caso).encode(),
                                       file_name=f"informe_{(nombre or 'inmueble').replace(' ','_').lower()}.txt",
                                       mime="text/plain", use_container_width=True, key="dl_s")

    # ══════════════════════════════
    # MODO 2: SOLO BIENES COMUNES
    # ══════════════════════════════
    elif modo_key == "comunes":
        st.markdown("#### Bienes y espacios comunes")
        st.info("**Ley 21.442, art. 43** — Seguro obligatorio de la comunidad. Cálculo independiente del seguro de cada unidad privada.")
        st.caption("Incluye: estructura, fachadas, instalaciones centrales, ascensores, subterráneos, piscina, áreas verdes, pasillos y estacionamientos comunes.")
        if not datos_ok:
            st.info("Complete primero zona, pisos y año de construcción.")
            d = None
        else:
            d = ui_comp("bc", zona, pisos, anio, aplica_iva, default_tipo="Comunidad",
                        label_tipo="Tipo (bienes comunes)")

        if st.button("Calcular bienes comunes", type="primary", use_container_width=True, key="btn_bc"):
            errs = [] if datos_ok else ["Complete zona, pisos y año."]
            if d: errs += validar_comp(d, "bienes comunes")
            for e in errs: st.error(f"⚠️ {e}")
            if not errs:
                res = calcular_vr(d["vub"], d["sup"], zona, pisos, anio, aplica_iva)
                ui_show("Bienes y espacios comunes", res,
                        {**d, "zona": zona, "pisos": pisos, "anio": anio}, danio_pct,
                        nota="Asegurado: la comunidad / condominio (Ley 21.442 art. 43 — OBLIGATORIO)")
                caso = dict(nombre=nombre or "Sin nombre", direccion=direccion or "—",
                            zona=zona, pisos=pisos, anio=anio, danio_pct=danio_pct,
                            modo="comunes",
                            comp={**d, "res": res, "zona": zona, "pisos": pisos, "anio": anio},
                            total_vr=res["vr"], total_monto=d["monto"] or 0)
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("💾 Guardar", use_container_width=True, key="g_bc"):
                        st.session_state.setdefault("casos", []).append(caso)
                        st.success("Caso guardado.")
                with b2:
                    st.download_button("📄 Descargar informe", data=generar_informe(caso).encode(),
                                       file_name=f"informe_{(nombre or 'comunes').replace(' ','_').lower()}.txt",
                                       mime="text/plain", use_container_width=True, key="dl_bc")

    # ══════════════════════════════
    # MODO 3: COMUNIDAD COMPLETA
    # ══════════════════════════════
    else:
        st.markdown("""> **NCG 556 CMF (dic. 2025)** — La póliza colectiva debe estructurarse en dos bloques separados:
> - **Bloque 1 — Bienes comunes:** asegurado es la *comunidad*. Obligatorio.
> - **Bloque 2 — Unidades privadas:** asegurado es cada *copropietario*. Opcional en póliza colectiva.""")

        if not datos_ok:
            st.info("Complete primero zona, pisos y año de construcción.")

        st.markdown("---")
        st.markdown("#### Bloque 1 — Bienes y espacios comunes")
        st.caption("Estructura, fachadas, instalaciones centrales, ascensores, subterráneos, áreas verdes y toda área de dominio común.")
        d_comun = ui_comp("c_bc", zona, pisos, anio, aplica_iva,
                          default_tipo="Comunidad", label_tipo="Tipo (bienes comunes)") if datos_ok else None

        st.markdown("---")
        st.markdown("#### Bloque 2 — Unidades privadas")
        st.caption("Cada departamento, local, bodega u oficina. VUB con tipo **Depto** (no Comunidad), ya que corresponde al valor de la unidad habitable sin áreas comunes.")

        incluir_uni = st.checkbox("Incluir unidades privadas en este análisis", value=True,
                                  help="Desmarque si las unidades tienen seguros individuales separados.")
        datos_uni = []
        if incluir_uni and datos_ok:
            if "n_uni" not in st.session_state: st.session_state.n_uni = 1
            ca, cr = st.columns(2)
            with ca:
                if st.button("➕ Agregar unidad", use_container_width=True): st.session_state.n_uni += 1
            with cr:
                if st.button("➖ Quitar última", use_container_width=True,
                             disabled=st.session_state.n_uni <= 1): st.session_state.n_uni -= 1
            for i in range(st.session_state.n_uni):
                with st.expander(f"Unidad privada {i+1}", expanded=(i == 0)):
                    nom_u = st.text_input("Identificación", key=f"u_{i}_nom",
                                          placeholder="Ej: Depto 501, Local 2")
                    du = ui_comp(f"u_{i}", zona, pisos, anio, aplica_iva,
                                 default_tipo="Depto", label_tipo="Tipo de unidad")
                    du["nombre"] = nom_u
                    du["poliza_propia"] = st.checkbox(
                        "Tiene póliza propia vigente (hipotecaria u otra)", key=f"u_{i}_prop",
                        help="Puede renunciar a cobertura en póliza colectiva (Ley 21.442 art. 43 b), pero igual contribuye a bienes comunes.")
                    datos_uni.append(du)
        elif incluir_uni and not datos_ok:
            st.info("Complete los datos generales para habilitar las unidades.")

        st.divider()
        if st.button("Calcular comunidad completa", type="primary", use_container_width=True, key="btn_com"):
            errs = [] if datos_ok else ["Complete zona, pisos y año."]
            if d_comun: errs += validar_comp(d_comun, "bienes comunes")
            else: errs += ["Complete los datos de bienes comunes."]
            if incluir_uni:
                for i, du in enumerate(datos_uni, 1): errs += validar_comp(du, f"unidad {i}")
            for e in errs: st.error(f"⚠️ {e}")

            if not errs:
                res_c = calcular_vr(d_comun["vub"], d_comun["sup"], zona, pisos, anio, aplica_iva)
                comp_c = {**d_comun, "res": res_c, "zona": zona, "pisos": pisos, "anio": anio}

                units_calc = []
                for du in datos_uni:
                    r_u = calcular_vr(du["vub"], du["sup"], zona, pisos, anio, aplica_iva)
                    units_calc.append({**du, "res": r_u, "zona": zona, "pisos": pisos, "anio": anio})

                vr_comun = res_c["vr"]
                vr_units = sum(u["res"]["vr"] for u in units_calc)
                vr_total = vr_comun + vr_units
                m_comun  = d_comun["monto"] or 0
                m_units  = sum(u.get("monto") or 0 for u in datos_uni)
                m_total  = m_comun + m_units
                ratio_t, infra_t = evaluar_poliza(m_total, vr_total)
                danio_t  = vr_total * (danio_pct / 100)
                indemn_t = indemn_proporcional(danio_t, m_total, vr_total)

                st.divider()
                st.subheader("Resultados")
                st.markdown("##### Resumen consolidado")
                if m_total <= 0:
                    st.info("ℹ️ Sin monto asegurado. El valor calculado indica cuánto debería asegurarse.")
                elif infra_t:
                    st.warning(f"⚠️ **Infraseguro global.** Cobertura: **{ratio_t*100:.1f}%** — Brecha: **{vr_total-m_total:,.2f} UF**")
                else:
                    st.success(f"✅ Cobertura global adecuada ({ratio_t*100:.1f}%)")

                t1, t2, t3, t4 = st.columns(4)
                t1.metric("VR total comunidad", f"{vr_total:,.2f} UF")
                t2.metric("Bienes comunes",      f"{vr_comun:,.2f} UF")
                t3.metric("Unidades privadas",   f"{vr_units:,.2f} UF")
                t4.metric("Cobertura global",
                          f"{ratio_t*100:.1f}%" if m_total > 0 else "—",
                          delta=f"{(ratio_t-1)*100:.1f}%" if m_total > 0 else None,
                          delta_color="normal" if not infra_t else "inverse")
                if m_total > 0:
                    st.progress(min(ratio_t, 1.0), text=f"Cobertura global: {ratio_t*100:.1f}%")

                with st.expander(f"🔥 Simulación total — daño del {danio_pct}%"):
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.metric("Daño total", f"{danio_t:,.2f} UF")
                    sc2.metric("Indemnización global", f"{indemn_t:,.2f} UF" if m_total > 0 else "—")
                    if infra_t and m_total > 0:
                        sc3.metric("Pérdida no cubierta", f"{danio_t-indemn_t:,.2f} UF", delta_color="inverse")

                # Tabla comparativa
                st.markdown("---")
                st.markdown("##### Tabla comparativa")
                filas = []
                r_c2, i_c2 = evaluar_poliza(m_comun, vr_comun)
                filas.append({"Componente": "Bienes comunes", "Asegurado": "Comunidad",
                              "Sup. m²": f"{d_comun['sup']:,.0f}", "VUB (UF/m²)": f"{d_comun['vub']:.1f}",
                              "VR (UF)": f"{vr_comun:,.2f}",
                              "Asegurado (UF)": f"{m_comun:,.2f}" if m_comun > 0 else "—",
                              "Cobertura": f"{r_c2*100:.1f}%" if m_comun > 0 else "—",
                              "Estado": "⚠️" if i_c2 else ("✅" if m_comun > 0 else "ℹ️")})
                for u in units_calc:
                    vr_u = u["res"]["vr"]; m_u = u.get("monto") or 0
                    r_u, i_u = evaluar_poliza(m_u, vr_u)
                    pp = " (póliza propia)" if u.get("poliza_propia") else ""
                    filas.append({"Componente": u.get("nombre") or "Unidad",
                                  "Asegurado": f"Copropietario{pp}",
                                  "Sup. m²": f"{u['sup']:,.0f}", "VUB (UF/m²)": f"{u['vub']:.1f}",
                                  "VR (UF)": f"{vr_u:,.2f}",
                                  "Asegurado (UF)": f"{m_u:,.2f}" if m_u > 0 else "—",
                                  "Cobertura": f"{r_u*100:.1f}%" if m_u > 0 else "—",
                                  "Estado": "⚠️" if i_u else ("✅" if m_u > 0 else "ℹ️")})
                filas.append({"Componente": "TOTAL", "Asegurado": "—",
                              "Sup. m²": f"{(d_comun['sup'] or 0) + sum(u.get('sup') or 0 for u in datos_uni):,.0f}",
                              "VUB (UF/m²)": "—",
                              "VR (UF)": f"{vr_total:,.2f}",
                              "Asegurado (UF)": f"{m_total:,.2f}" if m_total > 0 else "—",
                              "Cobertura": f"{ratio_t*100:.1f}%" if m_total > 0 else "—",
                              "Estado": "⚠️" if infra_t else ("✅" if m_total > 0 else "ℹ️")})
                st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

                # Detalle por componente
                st.markdown("---")
                st.markdown("##### Detalle por componente")
                ui_show("Bienes y espacios comunes", res_c, comp_c, danio_pct,
                        nota="Asegurado: la comunidad (Ley 21.442 art. 43 — OBLIGATORIO)", expanded=True)
                for i, u in enumerate(units_calc, 1):
                    lbl   = u.get("nombre") or f"Unidad {i}"
                    nota_u = "Póliza propia — puede renunciar a cobertura en póliza colectiva" \
                        if u.get("poliza_propia") else "Asegurado: copropietario (NCG 556 Bloque 2)"
                    ui_show(lbl, u["res"], u, danio_pct, nota=nota_u, expanded=(i == 1))

                caso = dict(
                    nombre=nombre or "Sin nombre", direccion=direccion or "—",
                    zona=zona, pisos=pisos, anio=anio, danio_pct=danio_pct,
                    modo="comunidad",
                    comp_comun=comp_c,
                    unidades=[{**u, "nombre": u.get("nombre") or f"Unidad {j+1}"}
                               for j, u in enumerate(units_calc)],
                    vr_comun=vr_comun, vr_units=vr_units,
                    total_vr=vr_total, total_monto=m_total,
                )
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("💾 Guardar", use_container_width=True, key="g_com"):
                        st.session_state.setdefault("casos", []).append(caso)
                        st.success("Caso guardado.")
                with b2:
                    st.download_button("📄 Descargar informe", data=generar_informe(caso).encode(),
                                       file_name=f"informe_{(nombre or 'comunidad').replace(' ','_').lower()}.txt",
                                       mime="text/plain", use_container_width=True, key="dl_com")


# ══════════════════════════════════════════════════════════
# PESTAÑA: MIS CASOS
# ══════════════════════════════════════════════════════════
with tab_casos:
    casos = st.session_state.get("casos", [])
    if not casos:
        st.info("Aún no tiene casos guardados.")
    else:
        st.caption(f"{len(casos)} caso{'s' if len(casos)>1 else ''} guardado{'s' if len(casos)>1 else ''}")
        for i, c in enumerate(casos):
            vr_c = c["total_vr"]; m_c = c["total_monto"]
            r_c, inf_c = evaluar_poliza(m_c, vr_c)
            estado = "⚠️ Infraseguro" if inf_c else ("✅ Cubierto" if m_c > 0 else "ℹ️ Sin seguro")
            modos  = {"simple": "Completo", "comunes": "Bienes comunes", "comunidad": "Comunidad"}
            with st.expander(f"{estado}  |  {c['nombre']}  —  {vr_c:,.2f} UF  [{modos.get(c['modo'],'—')}]"):
                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("Valor de reconstrucción", f"{vr_c:,.2f} UF")
                cc2.metric("Monto asegurado", f"{m_c:,.2f} UF" if m_c > 0 else "No indicado")
                cc3.metric("Cobertura", f"{r_c*100:.1f}%" if m_c > 0 else "—")
                st.caption(f"{c.get('zona','—')} · {c.get('pisos','—')} pisos · año {c.get('anio','—')}")
                st.download_button("📄 Descargar informe", data=generar_informe(c).encode(),
                                   file_name=f"informe_{c['nombre'].replace(' ','_').lower()}.txt",
                                   mime="text/plain", key=f"dl_caso_{i}")
        if st.button("🗑️ Limpiar todos los casos"):
            st.session_state.casos = []
            st.rerun()


# ══════════════════════════════════════════════════════════
# PESTAÑA: MARCO NORMATIVO
# ══════════════════════════════════════════════════════════
with tab_como:
    st.subheader("¿Qué es el VUB y de dónde viene?")
    st.markdown("""
El **Valor Unitario Base (VUB)** es el costo de construcción en UF por metro cuadrado.
Es el parámetro más importante del cálculo y **no existe una tabla oficial única en UF para seguros**.

En la práctica, los profesionales del sector lo obtienen de:

| Fuente | Descripción | Limitación |
|--------|-------------|------------|
| **Tabla MINVU** (oficial) | Publicada trimestralmente por el Ministerio de Vivienda. Base para permisos municipales. | Está en **pesos**, no en UF. Requiere conversión y criterio técnico. |
| **Tasador habilitado** | Profesional que calcula el VUB para el inmueble específico. | Tiene costo, pero es el más preciso. |
| **Corredor de seguros** | Usa tablas propias validadas por la compañía aseguradora. | Varía por compañía. |
| **Referencias de mercado** | Rangos estimados basados en estudios de mercado y constructoras. | Solo orientativos, no vinculantes. |

📎 La tabla oficial MINVU se actualiza cada trimestre en:
[minvu.gob.cl/elementos-tecnicos/tabla-de-costos-unitarios/](https://www.minvu.gob.cl/elementos-tecnicos/tabla-de-costos-unitarios/)
""")

    st.subheader("Rangos de referencia de mercado 2025–2026")
    st.caption(
        "Estimaciones basadas en datos de constructoras, arquitectos y corredores de seguros. "
        "**Son referenciales** — no reemplazan tasación profesional ni tabla MINVU oficial."
    )

    zona_ref = st.selectbox("Ver referencias para zona:", list(FACTOR_GEOGRAFICO.keys()), key="zona_ref")
    zona_corta_ref = ZONA_LABEL_CORTA.get(zona_ref, "")
    filas_ref = []
    for (zc, ts), niveles in REFERENCIAS_VUB.items():
        if zc != zona_corta_ref: continue
        for niv, rng in niveles.items():
            if rng:
                filas_ref.append({
                    "Tipo / Sistema":  ts,
                    "Nivel":           niv,
                    "Mín (UF/m²)":     rng[0],
                    "Máx (UF/m²)":     rng[1],
                    "Promedio ref.":   round((rng[0]+rng[1])/2, 1),
                    "Fuente":          "Mercado 2025–2026 (referencial)",
                })
    if filas_ref:
        st.dataframe(pd.DataFrame(filas_ref).sort_values(["Tipo / Sistema","Nivel"]),
                     use_container_width=True, hide_index=True)

    with st.expander("¿Por qué varían los valores entre zonas?"):
        st.markdown("""
- **Metropolitana:** mayor demanda de mano de obra, costos logísticos más bajos por proximidad a proveedores.
- **Intermedia:** costos moderados. Ciudades como Concepción, Valparaíso y Temuco tienen mercados locales establecidos.
- **Aislada:** el transporte de materiales y la escasez de mano de obra especializada encarecen la construcción. Antofagasta, por ejemplo, tiene algunos de los costos más altos del país. Aysén y Magallanes también presentan sobrecostos significativos.
""")

    st.subheader("Marco normativo")
    with st.expander("Ley 21.442 — Copropiedad Inmobiliaria (2022) — Art. 43"):
        st.markdown("""
Obliga a todo condominio con destino habitacional a contratar y mantener un **seguro colectivo contra incendio** que cubra:
- **Obligatoriamente:** bienes e instalaciones comunes.
- **Opcionalemente:** unidades privadas de copropietarios.

El copropietario puede renunciar a la cobertura de su unidad en la póliza colectiva si tiene póliza propia vigente, pero **no puede eximirse del pago por bienes comunes**.
""")

    with st.expander("NCG 556 CMF — Norma de Carácter General (diciembre 2025)"):
        st.markdown("""
Regula técnicamente los seguros del art. 43 Ley 21.442. Exige que la póliza colectiva se estructure en **dos bloques separados** con montos y deducibles claramente identificados:

| Bloque | Cubre | Asegurado | Carácter |
|--------|-------|-----------|----------|
| **1 — Bienes comunes** | Estructura, instalaciones, áreas comunes | La comunidad | Obligatorio |
| **2 — Unidades privadas** | Cada depto, local, bodega | El copropietario | Opcional en póliza colectiva |

Ante daños parciales en una unidad, la indemnización se destina **primero a reparación**, no al crédito hipotecario.
""")

    with st.expander("CCom Art. 553 — Regla proporcional"):
        st.markdown("""
Si el monto asegurado es menor al valor real, la compañía paga solo en proporción:

> Asegura el **70%** del valor real → recibirá solo el **70%** del daño, aunque sea parcial.

**Por eso es fundamental calcular y asegurar el valor correcto.**
""")

    with st.expander("Pasos del cálculo de VR"):
        st.markdown("""
| Paso | Concepto | Detalle |
|------|----------|---------|
| 1 | **VUB** (ingresado) | Costo en UF/m² según tipo, sistema y terminaciones |
| 2 | × Factor geográfico | Metropolitana 1.05 / Intermedia 1.00 / Aislada 1.15 |
| 3 | × Factor normativo | Antes 1985: 1.15 / 1985–2000: 1.10 / 2001–2010: 1.05 / desde 2011: 1.00 |
| 4 | × Factor altura | 1–2 pisos: 1.00 / 3–5: 1.05 / 6–10: 1.10 / 11+: 1.15 |
| 5 | = **Costo directo** | m² × VUB × fg × fn × fa |
| 6 | + Indirectos 31% | Diseño 3% + GG 6% + Utilidad 12% + Imprevistos 10% |
| 7 | + IVA 19% | Si corresponde |
| ✓ | = **Valor de reconstrucción** | |
""")

    st.divider()
    st.caption("Programa referencial. No reemplaza tasación profesional. Consulte a un corredor o tasador certificado.")
