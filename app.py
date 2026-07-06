import re
import base64
import streamlit as st
import pandas as pd
import gspread
import unicodedata

from pathlib import Path
from urllib.parse import quote
from google.oauth2.service_account import Credentials

# ==================================================
# CONFIGURACIÓN
# ==================================================

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"

APP_LOGO = ASSETS_DIR / "logo_proa_racional.png"

JSON_CREDENTIALS = "proa-cliesp-720c42cf544d.json"

NOMBRE_HOJA_RESPUESTAS = "Respuestas de formulario 1"

CLINICAS = {
    "Clínica de Especialistas": {
        "sheet_id": "1H_mDnO20m931Q8YkWPKYxC_vsbsP6g8fTq1h3GvJj0M",
        "worksheet": NOMBRE_HOJA_RESPUESTAS,
        "logo": ASSETS_DIR / "logo_proa_ce.png"
    },
    "Clínica el Laguito": {
        "sheet_id": "1x4A5MyT20re_ipwuEMRx3s_4RO0AflEWUAIYFLDwAaQ",
        "worksheet": NOMBRE_HOJA_RESPUESTAS,
        "logo": ASSETS_DIR / "logo_proa_cl.png"
    },
    "Hospital Soata": {
        "sheet_id": "14ZyLEWMjVcRjlidKI0qmmCYylurawpB8JWwZnq9Ec8E",
        "worksheet": NOMBRE_HOJA_RESPUESTAS,
        "logo": ASSETS_DIR / "logo_proa_hsas.png"
    }
}

SERVICIO_COL = "Servicio Tratante (El que indica el uso del antimicrobiano)"

ATB_COL = "Antimicrobiano Solicitado \n****ES EL ANTIMICROBIANO CONTROLADO QUE SE VA A INICIAR CON ESTA SOLICITUD***"

CONDUCTA_COL = "Conducta PROA"

CASO_COL = "# caso PROA"

FECHA_COL = "Fecha"

CONDUCTA_PENDIENTE_CULTIVO = "Aval, Pendiente cultivo"

OBSERVACION_COL = "Obervacion del diagnostico (Datos especificos, localizacion, complicacion)"

CULTIVOS_COL = "Cultivos o pruebas microbiológicas (PCR Multiplex, Antigenos, Anticuerpos)"

RESULTADO_CULTIVOS_COL = "Resultado de cultivos o Pruebas Microbiológicas  (Preliminar o definitivo)"

COLUMNAS_ESPERADAS = [
    SERVICIO_COL,
    ATB_COL,
    CONDUCTA_COL,
    CASO_COL,
    FECHA_COL,
    "Nombre del Paciente",
    "Documento",
    "Edad",
    "Cama",
    "Diagnostico Infeccioso",
    OBSERVACION_COL,
    "Creatinina",
    "Peso",
    RESULTADO_CULTIVOS_COL,
    CULTIVOS_COL
]

COLUMNAS_ALTERNATIVAS = {
    SERVICIO_COL: [
        "Servicio Tratante",
        "Servicio tratante",
        "Servicio",
        "Servicio Tratante El que indica el uso del antimicrobiano",
        "Servicio que indica el uso del antimicrobiano",
        "Servicio tratante que indica el uso del antimicrobiano",
        "Servicio donde se indica el uso del antimicrobiano"
    ],
    ATB_COL: [
        "Antimicrobiano Solicitado",
        "Antimicrobiano solicitado",
        "Antimicrobiano",
        "Antibiotico solicitado",
        "Antibiótico solicitado"
    ],
    OBSERVACION_COL: [
        "Observacion del diagnostico (Datos especificos, localizacion, complicacion)",
        "Observación del diagnóstico (Datos específicos, localización, complicación)",
        "Observacion del diagnostico",
        "Observación del diagnóstico"
    ],
    RESULTADO_CULTIVOS_COL: [
        "Resultado de cultivos o Pruebas Microbiologicas (Preliminar o definitivo)",
        "Resultado de cultivos o Pruebas Microbiológicas (Preliminar o definitivo)",
        "Resultado de cultivos o pruebas microbiologicas",
        "Resultado de cultivos o pruebas microbiológicas",
        "Resultado de cultivos",
        "Resultado cultivos"
    ],
    CULTIVOS_COL: [
        "Cultivos o pruebas microbiologicas (PCR Multiplex, Antigenos, Anticuerpos)",
        "Cultivos o pruebas microbiológicas",
        "Cultivos",
        "Pruebas microbiologicas",
        "Pruebas microbiológicas"
    ]
}

# ==================================================
# GOOGLE SHEETS
# ==================================================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)

# ==================================================
# STREAMLIT
# ==================================================

st.set_page_config(
    page_title="PROA Racional",
    page_icon="🦠",
    layout="wide"
)

# ==================================================
# FUNCIONES
# ==================================================

def normalizar_texto(nombre):
    texto = str(nombre)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = texto.replace("*", " ")
    texto = re.sub(r"[^a-zA-Z0-9#]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip().lower()


def columnas_equivalentes(encabezado, columna_esperada):
    encabezado_norm = normalizar_texto(encabezado)
    esperada_norm = normalizar_texto(columna_esperada)

    if encabezado_norm == esperada_norm:
        return True

    for alternativa in COLUMNAS_ALTERNATIVAS.get(columna_esperada, []):
        if encabezado_norm == normalizar_texto(alternativa):
            return True

    if columna_esperada == SERVICIO_COL:
        return (
            "servicio" in encabezado_norm
            and (
                "tratante" in encabezado_norm
                or "indica" in encabezado_norm
                or "antimicrobiano" in encabezado_norm
            )
        )

    if columna_esperada == ATB_COL:
        return (
            "antimicrobiano" in encabezado_norm
            or "antibiotico" in encabezado_norm
        ) and "solicitado" in encabezado_norm

    if columna_esperada == OBSERVACION_COL:
        return (
            "observacion" in encabezado_norm
            and "diagnostico" in encabezado_norm
        )

    if columna_esperada == RESULTADO_CULTIVOS_COL:
        return (
            "resultado" in encabezado_norm
            and (
                "cultivo" in encabezado_norm
                or "microbiologica" in encabezado_norm
                or "microbiologicas" in encabezado_norm
            )
        )

    if columna_esperada == CULTIVOS_COL:
        return (
            "resultado" not in encabezado_norm
            and (
                "cultivo" in encabezado_norm
                or "microbiologica" in encabezado_norm
                or "microbiologicas" in encabezado_norm
            )
        )

    return False


def normalizar_columnas_esperadas(encabezados):
    columnas_normalizadas = []

    for encabezado in encabezados:
        columna_final = encabezado

        for columna_esperada in COLUMNAS_ESPERADAS:
            if columnas_equivalentes(encabezado, columna_esperada):
                columna_final = columna_esperada
                break

        columnas_normalizadas.append(columna_final)

    return columnas_normalizadas


@st.cache_data(ttl=60)
def cargar_datos(sheet_id, worksheet_name, version_columnas="v5"):
    sheet = client.open_by_key(
        sheet_id
    ).worksheet(
        worksheet_name
    )

    valores = sheet.get_all_values()

    if not valores:
        return pd.DataFrame()

    encabezados = valores[0]
    encabezados = normalizar_columnas_esperadas(encabezados)

    filas = []

    for fila in valores[1:]:
        if len(fila) < len(encabezados):
            fila = fila + [""] * (len(encabezados) - len(fila))

        filas.append(
            fila[:len(encabezados)]
        )

    df = pd.DataFrame(
        filas,
        columns=encabezados
    )

    if df.columns.duplicated().any():
        df = df.T.groupby(level=0).first().T

    return df


def asegurar_columna(df, nombre_columna, valor_default=""):
    if nombre_columna not in df.columns:
        df[nombre_columna] = valor_default

    return df


def obtener_fila_por_caso(sheet, codigo_caso):
    valores = sheet.get_all_values()

    for fila_num, fila in enumerate(valores, start=1):
        if len(fila) > 24:
            if str(fila[24]).strip() == str(codigo_caso).strip():
                return fila_num

    return None


def obtener_indice_columna(sheet, nombre_columna):
    encabezados = sheet.row_values(1)

    for i, encabezado in enumerate(encabezados, start=1):
        if columnas_equivalentes(encabezado, nombre_columna):
            return i

    return None


def actualizar_campo(sheet, fila, nombre_columna, valor):
    columna = obtener_indice_columna(
        sheet,
        nombre_columna
    )

    if columna is not None:
        sheet.update_cell(
            fila,
            columna,
            valor
        )


@st.cache_data
def imagen_a_base64(ruta_imagen):
    with open(ruta_imagen, "rb") as archivo:
        return base64.b64encode(archivo.read()).decode("utf-8")


def obtener_institucion_desde_url():
    institucion = st.query_params.get("institucion")

    if isinstance(institucion, list):
        institucion = institucion[0] if institucion else None

    if institucion in CLINICAS:
        return institucion

    return list(CLINICAS.keys())[0]


def mostrar_selector_institucion():
    institucion_seleccionada = obtener_institucion_desde_url()

    st.markdown(
        """
        <style>
            .selector-logos {
                display: flex;
                align-items: center;
                gap: 18px;
                flex-wrap: wrap;
                margin: 8px 0 22px 0;
            }

            .tarjeta-logo {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 250px;
                height: 92px;
                padding: 10px;
                border: 2px solid rgba(255, 255, 255, 0.16);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.035);
                transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease;
                text-decoration: none;
            }

            .tarjeta-logo:hover {
                transform: translateY(-2px);
                border-color: rgba(255, 91, 91, 0.72);
                background: rgba(255, 255, 255, 0.07);
            }

            .tarjeta-logo.seleccionada {
                width: 310px;
                height: 116px;
                border-color: #ff5b5b;
                background: rgba(255, 91, 91, 0.13);
                box-shadow: 0 0 0 2px rgba(255, 91, 91, 0.22);
            }

            .tarjeta-logo img {
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
                border-radius: 4px;
            }

            .logo-principal {
                max-width: 360px;
                width: 100%;
                height: auto;
                margin-bottom: 16px;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    tarjetas = []

    for nombre, configuracion in CLINICAS.items():
        clase = "tarjeta-logo seleccionada" if nombre == institucion_seleccionada else "tarjeta-logo"
        logo_base64 = imagen_a_base64(configuracion["logo"])
        institucion_url = quote(nombre)

        tarjetas.append(
            f'<a class="{clase}" href="?institucion={institucion_url}" title="{nombre}">'
            f'<img src="data:image/png;base64,{logo_base64}" alt="{nombre}">'
            f'</a>'
        )

    st.markdown(
        '<div class="selector-logos">' + "".join(tarjetas) + "</div>",
        unsafe_allow_html=True
    )

    return institucion_seleccionada


def mostrar_logo_principal():
    if APP_LOGO.exists():
        logo_base64 = imagen_a_base64(APP_LOGO)

        st.markdown(
            f'<img class="logo-principal" src="data:image/png;base64,{logo_base64}" alt="PROA Racional">',
            unsafe_allow_html=True
        )
    else:
        st.title("PROA Racional")

# ==================================================
# APP
# ==================================================

try:
    mostrar_logo_principal()

    st.markdown("**Seleccione la institución**")

    institucion_seleccionada = mostrar_selector_institucion()

    configuracion_institucion = CLINICAS[institucion_seleccionada]
    sheet_id = configuracion_institucion["sheet_id"]
    worksheet_name = configuracion_institucion["worksheet"]

    st.caption(
        f"Auditoría de prescripciones - {institucion_seleccionada}"
    )

    if sheet_id.startswith("PEGA_AQUI"):
        st.warning(
            f"Falta configurar el ID de Google Sheets para {institucion_seleccionada}."
        )
        st.stop()

    df = cargar_datos(
        sheet_id,
        worksheet_name,
        version_columnas="v5"
    )

    df = asegurar_columna(df, SERVICIO_COL, "Sin servicio registrado")
    df = asegurar_columna(df, ATB_COL, "Sin antimicrobiano registrado")
    df = asegurar_columna(df, CONDUCTA_COL, "")
    df = asegurar_columna(df, CASO_COL, "")
    df = asegurar_columna(df, FECHA_COL, "")
    df = asegurar_columna(df, "Nombre del Paciente", "")
    df = asegurar_columna(df, "Documento", "")
    df = asegurar_columna(df, "Edad", "")
    df = asegurar_columna(df, "Cama", "")
    df = asegurar_columna(df, "Diagnostico Infeccioso", "")
    df = asegurar_columna(df, OBSERVACION_COL, "")
    df = asegurar_columna(df, "Creatinina", "")
    df = asegurar_columna(df, "Peso", "")
    df = asegurar_columna(df, RESULTADO_CULTIVOS_COL, "")
    df = asegurar_columna(df, CULTIVOS_COL, "")

    df[FECHA_COL] = pd.to_datetime(
        df[FECHA_COL],
        dayfirst=True,
        errors="coerce"
    )

    fecha_inicio = pd.Timestamp(
        "2026-06-01"
    )

    df = df[
        df[FECHA_COL] >= fecha_inicio
    ]

    conducta_normalizada = (
        df[CONDUCTA_COL]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    pendientes = df[
        conducta_normalizada.eq("")
        | conducta_normalizada.eq(CONDUCTA_PENDIENTE_CULTIVO)
    ]

    st.info(
        "Mostrando únicamente casos pendientes desde el 01/06/2026"
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Casos Totales",
            len(df)
        )

    with col2:
        st.metric(
            "Pendientes",
            len(pendientes)
        )

    with col3:
        st.metric(
            "Evaluados",
            len(df) - len(pendientes)
        )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        servicios = sorted(
            pendientes[SERVICIO_COL]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        servicio = st.selectbox(
            "Servicio",
            ["Todos"] + servicios
        )

    with col2:
        antibioticos = sorted(
            pendientes[ATB_COL]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        antibiotico = st.selectbox(
            "Antimicrobiano",
            ["Todos"] + antibioticos
        )

    if servicio != "Todos":
        pendientes = pendientes[
            pendientes[SERVICIO_COL] == servicio
        ]

    if antibiotico != "Todos":
        pendientes = pendientes[
            pendientes[ATB_COL] == antibiotico
        ]

    st.subheader("📋 Casos Pendientes")

    columnas_tabla = [
        CASO_COL,
        FECHA_COL,
        "Nombre del Paciente",
        SERVICIO_COL,
        "Diagnostico Infeccioso",
        ATB_COL
    ]

    tabla_pendientes = pendientes[columnas_tabla].copy()

    pendiente_cultivo = (
        pendientes[CONDUCTA_COL]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq(CONDUCTA_PENDIENTE_CULTIVO)
    )

    def resaltar_pendiente_cultivo(fila):
        if pendiente_cultivo.loc[fila.name]:
            return [
                "background-color: #fff3cd; color: #3b2f00"
                for _ in fila
            ]

        return [
            ""
            for _ in fila
        ]

    st.dataframe(
        tabla_pendientes.style.apply(
            resaltar_pendiente_cultivo,
            axis=1
        ),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    casos = (
        pendientes[CASO_COL]
        .dropna()
        .astype(str)
        .tolist()
    )

    if len(casos) > 0:
        caso_seleccionado = st.selectbox(
            "Seleccionar Caso",
            casos
        )

        caso = pendientes[
            pendientes[CASO_COL].astype(str)
            == str(caso_seleccionado)
        ].iloc[0]

        st.subheader("🔎 Información Clínica")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Paciente:**", caso["Nombre del Paciente"])
            st.write("**Documento:**", caso["Documento"])
            st.write("**Edad:**", caso["Edad"])
            st.write("**Cama:**", caso["Cama"])
            st.write("**Servicio:**", caso[SERVICIO_COL])
            st.write("**Diagnóstico:**", caso["Diagnostico Infeccioso"])
            st.write("**Observación diagnóstico:**", caso[OBSERVACION_COL])

        with col2:
            st.write("**Antimicrobiano:**", caso[ATB_COL])
            st.write("**Creatinina:**", caso["Creatinina"])
            st.write("**Peso:**", caso["Peso"])
            st.write("**Cultivos:**", caso[CULTIVOS_COL])

            cultivos_normalizado = normalizar_texto(caso[CULTIVOS_COL])

            if (
                "si" in cultivos_normalizado
                and "resultado" in cultivos_normalizado
                and "disponible" in cultivos_normalizado
            ):
                resultado_cultivos = str(caso[RESULTADO_CULTIVOS_COL]).strip()

                st.write(
                    "**Resultado cultivos:**",
                    resultado_cultivos if resultado_cultivos else "Sin resultado registrado"
                )

        st.divider()

        st.subheader("🩺 Evaluación PROA")

        opciones_evaluacion_proa = [
            "SI",
            "NO",
            "NO APLICA"
        ]

        col1, col2 = st.columns(2)

        with col1:
            valoracion_uci = st.selectbox(
                "Valoración UCI",
                opciones_evaluacion_proa,
                index=2,
                key=f"valoracion_uci_{caso_seleccionado}"
            )

            ajuste_uci = st.selectbox(
                "Ajuste en UCI",
                opciones_evaluacion_proa,
                index=2,
                key=f"ajuste_uci_{caso_seleccionado}"
            )

            ajuste_cultivo = st.selectbox(
                "Ajuste por cultivo",
                opciones_evaluacion_proa,
                index=2,
                key=f"ajuste_cultivo_{caso_seleccionado}"
            )

            ajuste_infecto = st.selectbox(
                "Ajuste por Infectólogo",
                opciones_evaluacion_proa,
                index=2,
                key=f"ajuste_infecto_{caso_seleccionado}"
            )

        with col2:
            adherencia_itu = st.selectbox(
                "Adherencia ITU",
                opciones_evaluacion_proa,
                index=2,
                key=f"adherencia_itu_{caso_seleccionado}"
            )

            adherencia_nac = st.selectbox(
                "Adherencia NAC",
                opciones_evaluacion_proa,
                index=2,
                key=f"adherencia_nac_{caso_seleccionado}"
            )

            adherencia_epoc = st.selectbox(
                "Adherencia Guia EPOC",
                opciones_evaluacion_proa,
                index=2,
                key=f"adherencia_epoc_{caso_seleccionado}"
            )

            adherencia_iptb = st.selectbox(
                "Adherencia Guia IPTB",
                opciones_evaluacion_proa,
                index=2,
                key=f"adherencia_iptb_{caso_seleccionado}"
            )

            adherencia_eda = st.selectbox(
                "Adherencia Guia EDA",
                opciones_evaluacion_proa,
                index=2,
                key=f"adherencia_eda_{caso_seleccionado}"
            )

        mortalidad = st.selectbox(
            "Mortalidad IAAS MDR",
            opciones_evaluacion_proa,
            index=2,
            key=f"mortalidad_{caso_seleccionado}"
        )

        conducta = st.selectbox(
            "Conducta PROA",
            [
                "Aval",
                CONDUCTA_PENDIENTE_CULTIVO,
                "Suspender",
                "Desescalar",
                "Escalar",
                "Sin Intervención por PROA"
            ]
        )

        if st.button("💾 Guardar Evaluación"):
            hoja = client.open_by_key(
                sheet_id
            ).worksheet(
                worksheet_name
            )

            fila = obtener_fila_por_caso(
                hoja,
                caso_seleccionado
            )

            if fila is None:
                st.error(
                    "No fue posible localizar el caso."
                )

            else:
                actualizar_campo(hoja, fila, "Valoración UCI", valoracion_uci)
                actualizar_campo(hoja, fila, "Ajuste en UCI", ajuste_uci)
                actualizar_campo(hoja, fila, "Ajuste por cultivo", ajuste_cultivo)
                actualizar_campo(hoja, fila, "Ajuste por Infectólogo", ajuste_infecto)
                actualizar_campo(hoja, fila, "Adherencia ITU", adherencia_itu)
                actualizar_campo(hoja, fila, "Adherencia NAC", adherencia_nac)
                actualizar_campo(hoja, fila, "Adherencia Guia EPOC", adherencia_epoc)
                actualizar_campo(hoja, fila, "Adherencia Guia IPTB", adherencia_iptb)
                actualizar_campo(hoja, fila, "Adherencia Guia EDA", adherencia_eda)
                actualizar_campo(hoja, fila, "Mortalidad IAAS MDR", mortalidad)
                actualizar_campo(hoja, fila, "Conducta PROA", conducta)

                st.success(
                    "Evaluación guardada correctamente."
                )

                st.cache_data.clear()

                st.rerun()

    else:
        st.success(
            "No existen casos pendientes."
        )

except Exception as e:
    st.error(
        f"Error: {str(e)}"
    )