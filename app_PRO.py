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
            texto_pag = pagina.extract_text()
            if texto_pag:
                texto_completo += texto_pag + "\n"

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    # Detección para Endesa / Energía XXI
    es_endesa = re.search(r'Endesa|Energía\s*XXI|Comercializadora\s*de\s*Referencia', texto_completo, re.IGNORECASE)

    # Inicialización de variables por defecto
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
    potencia = 0.0
    fecha = "No encontrada"
    dias = 0
    total_real = 0.0
    excedente = 0.0

    if es_el_corte_ingles:
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        if match_cons:
            consumos['punta'] = float(match_cons.group(1).replace(',', '.'))
            consumos['llano'] = float(match_cons.group(2).replace(',', '.'))
            consumos['valle'] = float(match_cons.group(3).replace(',', '.'))
        
        m_pot = re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_fecha = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_total = re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo)
        total_real = float(m_total.group(1).replace(',', '.')) if m_total else 0.0

    elif es_repsol:
        m_fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_pot = re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_fijo = re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_ener = re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0) + (float(m_ener.group(1).replace(',', '.')) if m_ener else 0.0)
        m_cons = re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        consumos['punta'] = float(m_cons.group(1).replace(',', '.')) if m_cons else 0.0

    elif es_iberdrola:
        m_pot = re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_per = re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = m_per.group(2) if m_per else "No encontrada"
        m_p = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo); m_l = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo); m_v = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {'punta': float(m_p.group(1).replace(',', '.')) if m_p else 0.0, 'llano': float(m_l.group(1).replace(',', '.')) if m_l else 0.0, 'valle': float(m_v.group(1).replace(',', '.')) if m_v else 0.0}
        m_ip = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE); m_ie = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_ip.group(1).replace(',', '.')) if m_ip else 0.0) + (float(m_ie.group(1).replace(',', '.')) if m_ie else 0.0)

    elif es_endesa:
        # --- LÓGICA REFORZADA PARA ENDESA ---
        # 1. FECHA: Cualquier fecha DD/MM/AAAA en el documento (la primera suele ser la de emisión)
        fechas_detectadas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto_completo)
        fecha = fechas_detectadas[0] if fechas_detectadas else "No encontrada"

        # 2. POTENCIA: Buscamos el valor numérico que acompañe a 'kW'
        # Usamos un barrido para encontrar la potencia contratada típica (P1)
        match_pot = re.search(r'([\d,.]+)\s*kW', texto_completo)
        potencia = float(match_pot.group(1).replace(',', '.')) if match_pot else 0.0

        # 3. DÍAS
        match_dias = re.search(r'(\d+)\s*días', texto_completo, re.IGNORECASE)
        dias = int(match_dias.group(1)) if match_dias else 0

        # 4. CONSUMOS (Punta, Llano, Valle en orden de aparición kWh)
        kwh_detectados = re.findall(r'([\d,.]+)\s*kWh', texto_completo)
        if len(kwh_detectados) >= 3:
            consumos = {'punta': float(kwh_detectados[0].replace(',', '.')), 'llano': float(kwh_detectados[1].replace(',', '.')), 'valle': float(kwh_detectados[2].replace(',', '.'))}
        elif len(kwh_detectados) > 0:
            consumos['punta'] = float(kwh_detectados[0].replace(',', '.'))

        # 5. TOTAL: Buscamos el símbolo € cerca de la palabra total o subtotal
        match_total = re.search(r'(?:Total|Importe|Subtotal).*?([\d,.]+)\s*€', texto_completo, re.IGNORECASE | re.DOTALL)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    else:
        # Genérico para otros
        m_fecha = re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_pot = re.search(r'([\d,.]+)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'(\d+)\s*días', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_total = re.search(r'([\d,.]+)\s*€', texto_completo)
        total_real = float(m_total.group(1).replace(',', '.')) if m_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- INTERFAZ STREAMLIT ---
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
            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []
            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Dias_Factura": fact['Días']})
                for _, tarifa in df_tarifas.iterrows():
                    try:
                        coste_estimado = (fact['Días'] * pd.to_numeric(tarifa.iloc[1]) * fact['Potencia (kW)']) + \
                                         (fact['Días'] * pd.to_numeric(tarifa.iloc[2]) * fact['Potencia (kW)']) + \
                                         (fact['Consumo Punta (kWh)'] * pd.to_numeric(tarifa.iloc[3])) + \
                                         (fact['Consumo Llano (kWh)'] * pd.to_numeric(tarifa.iloc[4])) + \
                                         (fact['Consumo Valle (kWh)'] * pd.to_numeric(tarifa.iloc[5])) - \
                                         (fact['Excedente (kWh)'] * pd.to_numeric(tarifa.iloc[6]))
                        resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": tarifa.iloc[0], "Coste (€)": round(coste_estimado, 2), "Ahorro": round(fact['Total Real'] - coste_estimado, 2), "Dias_Factura": fact['Días']})
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            st.subheader("📊 Comparativa Detallada")
            st.dataframe(df_comp.drop(columns=['Dias_Factura'], errors='ignore'), use_container_width=True, hide_index=True)
