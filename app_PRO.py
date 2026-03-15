
import pdfplumber

import re

import pandas as pd

import streamlit as st

import io

import os



def extraer_datos_factura(pdf_path):

    texto_completo = ""

    with pdfplumber.open(pdf_path) as pdf:

        for pagina in pdf.pages:

            texto_completo += pagina.extract_text() + "\n"



    # 1. Búsqueda de Consumos (Soporte universal)

    patrones_consumo = {

        'punta': [

            r'Consumo\s+kWh\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+', 

            r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)', 

            r'Consumo\s+en\s+P1:?\s*([\d,.]+)',

            r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)'

        ],

        'llano': [

            r'Consumo\s+kWh\s+[\d,.]+\s+([\d,.]+)\s+[\d,.]+', 

            r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)', 

            r'Consumo\s+en\s+P2:?\s*([\d,.]+)',

            r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+[\d,.]+\s+([\d,.]+)'

        ],

        'valle': [

            r'Consumo\s+kWh\s+[\d,.]+\s+[\d,.]+\s+([\d,.]+)', 

            r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)', 

            r'Consumo\s+en\s+P3:?\s*([\d,.]+)',

            r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+[\d,.]+\s+[\d,.]+\s+([\d,.]+)'

        ]

    }

    

    consumos = {}

    for tramo, patrones in patrones_consumo.items():

        consumos[tramo] = 0.0

        for patron in patrones:

            match = re.search(patron, texto_completo, re.IGNORECASE)

            if match:

                consumos[tramo] = float(match.group(1).replace(',', '.'))

                break



    # 2. Búsqueda de Potencia (Ajustado para El Corte Inglés y Energía XXI)

    # Añadido patrón para "Potencia contratada X,XXX kW" sin dos puntos

    patron_potencia = r'(?:Potencia:?\s*Punta:?|Potencia\s+contratada\s+kW|Potencia\s+contratada|Potencia\s+P1:?)[\s\n]*([\d,.]+)'

    match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)

    potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0



    # 3. Fecha y Días (Ajuste para "Días de consumo:")

    patron_fecha = r'(?:Fecha\s+de\s+emisión:|emitida\s+el|Fecha\s+de\s+Factura:)\s*([\d/]+)'

    match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)

    fecha = match_fecha.group(1) if match_fecha else "No encontrada"



    # Buscamos específicamente "Días de consumo:" para ECI o el formato estándar

    patron_dias = r'(?:Días\s+de\s+consumo:|Periodo\s+de\s+consumo:.*?)\s*(\d+)'

    match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE | re.DOTALL)

    if not match_dias:

        match_dias = re.search(r'(\d+)\s*días', texto_completo, re.IGNORECASE)

    

    dias = int(match_dias.group(1)) if match_dias else 0



    # 4. Excedentes

    patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'

    match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)

    excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0

    

    # 5. Total Real

    total_real = 0.0

    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)

    if es_xxi:

        m_pot = re.search(r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)

        m_ene = re.search(r'por\s+energía\s+consumida\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)

        total_real = (float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0) + \

                     (float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0)

    else:

        patron_total = r'(?:TOTAL\s+FACTURA|Importe\s+total|Total\s+a\s+pagar|Total\s+factura)\s*:?\s*([\d,.]+)\s*€'

        match_total = re.search(patron_total, texto_completo, re.IGNORECASE)

        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0



    return {

        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,

        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],

        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,

        "Total Real": total_real

    }



# --- EL RESTO DEL CÓDIGO PERMANECE IGUAL ---

st.set_page_config(page_title="Comparador Energético", layout="wide")

st.title("⚡ Comparador de Facturas Eléctricas Pro")



excel_path = "tarifas_companias.xlsx"



if not os.path.exists(excel_path):

    st.error(f"No se encuentra el archivo '{excel_path}' en el repositorio.")

else:

    uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)



    if uploaded_files:

        datos_facturas = []

        for uploaded_file in uploaded_files:

            try:

                res = extraer_datos_factura(io.BytesIO(uploaded_file.read()))

                res['Archivo'] = uploaded_file.name

                datos_facturas.append(res)

            except Exception as e:

                st.error(f"Error procesando {uploaded_file.name}: {e}")



        if datos_facturas:

            df_resumen_pdfs = pd.DataFrame(datos_facturas)

            with st.expander("🔍 Ver detalles de datos extraídos"):

                st.dataframe(df_resumen_pdfs, use_container_width=True)



            df_tarifas = pd.read_excel(excel_path)

            resultados_finales = []



            for _, fact in df_resumen_pdfs.iterrows():

                resultados_finales.append({

                    "Mes/Fecha": fact['Fecha'],

                    "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",

                    "Coste (€)": fact['Total Real'],

                    "Ahorro": 0.0

                })



                for index, tarifa in df_tarifas.iterrows():

                    try:

                        nombre_cia = tarifa.iloc[0]

                        b_pot1 = pd.to_numeric(tarifa.iloc[1], errors='coerce')

                        c_pot2 = pd.to_numeric(tarifa.iloc[2], errors='coerce')

                        d_punta = pd.to_numeric(tarifa.iloc[3], errors='coerce')

                        e_llano = pd.to_numeric(tarifa.iloc[4], errors='coerce')

                        f_valle = pd.to_numeric(tarifa.iloc[5], errors='coerce')

                        g_excedente = pd.to_numeric(tarifa.iloc[6], errors='coerce')



                        coste_estimado = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + \

                                         (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + \

                                         (fact['Consumo Punta (kWh)'] * d_punta) + \

                                         (fact['Consumo Llano (kWh)'] * e_llano) + \

                                         (fact['Consumo Valle (kWh)'] * f_valle) - \

                                         (fact['Excedente (kWh)'] * g_excedente)

                        

                        ahorro = fact['Total Real'] - coste_estimado

                        resultados_finales.append({

                            "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia,

                            "Coste (€)": round(coste_estimado, 2), "Ahorro": round(ahorro, 2)

                        })

                    except: continue



            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])

            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Coste (€)"], ascending=[True, True])



            st.subheader("📊 Comparativa de Mercado")

            st.dataframe(

                df_comp,

                column_config={

                    "Mes/Fecha": "📅 Período",

                    "Compañía/Tarifa": "🏢 Proveedor / Opción",

                    "Coste (€)": st.column_config.ProgressColumn(

                        "Coste Mensual", format="%.2f €", min_value=0, max_value=float(df_comp["Coste (€)"].max()),

                    ),

                    "Ahorro": st.column_config.NumberColumn("Diferencia vs Actual", format="%.2f €")

                },

                hide_index=True, use_container_width=True

            )



            mejor = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].iloc[0]

            if mejor["Ahorro"] > 0:

                st.success(f"💡 **Oportunidad de Ahorro:** Cambiándote a **{mejor['Compañía/Tarifa']}** ahorrarías **{mejor['Ahorro']} €**.")

            else:

                st.info("✅ Tu tarifa actual parece ser la más competitiva.")
