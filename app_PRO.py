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

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)
    es_total_energies = re.search(r'TotalEnergies', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)
    es_octopus = re.search(r'octopus\s+energy', texto_completo, re.IGNORECASE)

    compania = "Genérica / Desconocida"
    total_real = 0.0

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        consumos = {
            'punta': float(match_cons.group(1).replace(',', '.')) if match_cons else 0.0,
            'llano': float(match_cons.group(2).replace(',', '.')) if match_cons else 0.0,
            'valle': float(match_cons.group(3).replace(',', '.')) if match_cons else 0.0
        }
        potencia = float(re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo) else 0.0
        fecha = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo).group(1)) if re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo) else 0
        total_real = float(re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo).group(1).replace(',', '.')) if re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo) else 0.0
        excedente = 0.0 

    elif es_xxi:
        compania = "Energía XXI"
        # 1. Extraer Consumos
        patrones_consumo = {'punta': r'P1:?\s*([\d,.]+)\s*kWh', 'llano': r'P2:?\s*([\d,.]+)\s*kWh', 'valle': r'P3:?\s*([\d,.]+)\s*kWh'}
        consumos = {tramo: float(re.search(patron, texto_completo, re.I).group(1).replace(',', '.')) if re.search(patron, texto_completo, re.I) else 0.0 for tramo, patron in patrones_consumo.items()}
        
        # 2. Extraer Potencia, Días y Fecha
        potencia = float(re.search(r'([\d,.]+)\s*kW', texto_completo).group(1).replace(',', '.')) if re.search(r'([\d,.]+)\s*kW', texto_completo) else 0.0
        dias = int(re.search(r'(\d+)\s*días', texto_completo).group(1)) if re.search(r'(\d+)\s*días', texto_completo) else 0
        fecha = re.search(r'Fecha\s+de\s+cargo:\s*([\d/]+|[\d]+\s+de\s+\w+)', texto_completo, re.I).group(1) if re.search(r'Fecha\s+de\s+cargo:\s*([\d/]+|[\d]+\s+de\s+\w+)', texto_completo, re.I) else "No encontrada"
        
        # 3. CORRECCIÓN CRÍTICA: Suma de Potencia + Energía (Ignorando comillas y saltos de línea)
        m_pot = re.search(r'Por\s+potencia\s+contratada\s*\"?,\s*\"?([\d,.]+)\s*€', texto_completo, re.I)
        m_ene = re.search(r'Por\s+energía\s+consumida\s*\"?,\s*\"?([\d,.]+)\s*€', texto_completo, re.I)
        
        v_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        v_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        total_real = v_pot + v_ene
        
        excedente = abs(float(re.search(r'excedentes\s*(?:-?[\d,.]+\s*€/kWh)?\s*(-?[\d,.]+)\s*kWh', texto_completo, re.I).group(1).replace(',', '.'))) if re.search(r'excedentes\s*(?:-?[\d,.]+\s*€/kWh)?\s*(-?[\d,.]+)\s*kWh', texto_completo, re.I) else 0.0

    elif es_octopus:
        compania = "Octopus Energy"
        fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'\((\d+)\s+días\)', texto_completo).group(1)) if re.search(r'\((\d+)\s+días\)', texto_completo) else 0
        potencia = float(re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo).group(1).replace(',', '.')) if re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo) else 0.0
        m_punta = re.search(r'Punta\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I)
        m_llano = re.search(r'Llano\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I)
        m_valle = re.search(r'Valle\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I)
        consumos = {'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0, 'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0, 'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0}
        total_real = (float(re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.I).group(1).replace(',', '.')) if re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.I) else 0.0) + (float(re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.I).group(1).replace(',', '.')) if re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.I) else 0.0)
        excedente = float(re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.I).group(1).replace(',', '.')) if re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.I) else 0.0

    # ... (Resto de compañías mantienen su lógica original) ...
    else:
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        potencia, dias, fecha, excedente = 0.0, 0, "No encontrada", 0.0

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos.get('punta', 0.0), "Consumo Llano (kWh)": consumos.get('llano', 0.0),
        "Consumo Valle (kWh)": consumos.get('valle', 0.0), "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- Código Streamlit ---
st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}'")
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
                st.error(f"Error en {uploaded_file.name}: {e}")

        if datos_facturas:
            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            cols = ["Compañía", "Fecha", "Días", "Potencia (kW)", "Consumo Punta (kWh)", "Consumo Llano (kWh)", "Consumo Valle (kWh)", "Excedente (kWh)", "Total Real", "Archivo"]
            df_resumen_pdfs = df_resumen_pdfs[cols]

            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Dias_Factura": fact['Días']})
                for _, tarifa in df_tarifas.iterrows():
                    try:
                        coste = (fact['Días'] * tarifa.iloc[1] * fact['Potencia (kW)']) + (fact['Días'] * tarifa.iloc[2] * fact['Potencia (kW)']) + \
                                (fact['Consumo Punta (kWh)'] * tarifa.iloc[3]) + (fact['Consumo Llano (kWh)'] * tarifa.iloc[4]) + \
                                (fact['Consumo Valle (kWh)'] * tarifa.iloc[5]) - (fact['Excedente (kWh)'] * tarifa.iloc[6])
                        resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": tarifa.iloc[0], "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2), "Dias_Factura": fact['Días']})
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            st.subheader("📊 Comparativa Detallada")
            st.dataframe(df_comp.drop(columns=['Dias_Factura']), use_container_width=True, hide_index=True)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="comparativa.xlsx", use_container_width=True)
