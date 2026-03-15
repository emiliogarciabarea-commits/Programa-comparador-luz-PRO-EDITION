
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

    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)

    if es_el_corte_ingles:
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        consumos = {
            'punta': float(match_cons.group(1).replace(',', '.')) if match_cons else 0.0,
            'llano': float(match_cons.group(2).replace(',', '.')) if match_cons else 0.0,
            'valle': float(match_cons.group(3).replace(',', '.')) if match_cons else 0.0
        }
        patron_potencia = r'Potencia\s+contratada\s+kW\s+([\d,.]+)'
        match_potencia = re.search(patron_potencia, texto_completo)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_fecha = r'Fecha\s+de\s+Factura:\s*([\d/]+)'
        match_fecha = re.search(patron_fecha, texto_completo)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"
        patron_dias = r'Días\s+de\s+consumo:\s*(\d+)'
        match_dias = re.search(patron_dias, texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_total = r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0
        excedente = 0.0 
    else:
        patrones_consumo = {
            'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh']
        }
        consumos = {}
        for tramo, patrones in patrones_consumo.items():
            consumos[tramo] = 0.0
            for patron in patrones:
                match = re.search(patron, texto_completo, re.IGNORECASE)
                if match:
                    consumos[tramo] = float(match.group(1).replace(',', '.'))
                    break
        patron_potencia = r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_fecha = r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})'
        match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"
        patron_dias = r'(\d+)\s*días'
        match_dias = re.search(patron_dias, texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
        match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
        excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
        es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)
        if es_xxi:
            m_pot = re.search(r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            m_ene = re.search(r'por\s+energía\s+consumida\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = (float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0) + (float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0)
        else:
            match_total = re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": total_real
    }

st.set_page_config(page_title="Comparador Energético Multi-Mes", layout="wide")
st.title("⚡ Comparador de Facturas: Análisis Acumulado")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}' en el repositorio.")
else:
    uploaded_files = st.file_uploader("Sube una o varias facturas PDF", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        datos_facturas = []
        for uploaded_file in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(uploaded_file.read()))
                datos_facturas.append(res)
            except Exception as e:
                st.error(f"Error procesando {uploaded_file.name}: {e}")

        if datos_facturas:
            df_pdfs = pd.DataFrame(datos_facturas)
            
            # --- CÁLCULOS ACUMULADOS DE TODAS LAS FACTURAS ---
            total_dias = df_pdfs['Días'].sum()
            total_pagado_real = df_pdfs['Total Real'].sum()
            potencia_media = df_pdfs['Potencia (kW)'].mean() # Usamos la media por si varía

            df_tarifas = pd.read_excel(excel_path)
            resumen_comparativo = []

            # 1. Añadir la situación actual (Total de todas las facturas)
            resumen_comparativo.append({
                "Compañía/Tarifa": "📍 TU GASTO ACTUAL (Total)",
                "Coste Total Facturas (€)": round(total_pagado_real, 2),
                "Ahorro Total (€)": 0.0,
                "Ahorro Anual Est. (€)": 0.0
            })

            # 2. Calcular coste en otras compañías para el MISMO periodo total
            for _, tarifa in df_tarifas.iterrows():
                try:
                    nombre_cia = tarifa.iloc[0]
                    b_pot1, c_pot2 = pd.to_numeric(tarifa.iloc[1:3], errors='coerce')
                    d_punta, e_llano, f_valle = pd.to_numeric(tarifa.iloc[3:6], errors='coerce')
                    g_excedente = pd.to_numeric(tarifa.iloc[6], errors='coerce')

                    # Calculamos el coste que habrían tenido todas las facturas juntas con esta nueva tarifa
                    coste_cia_total = 0
                    for _, f in df_pdfs.iterrows():
                        coste_cia_total += (f['Días'] * b_pot1 * f['Potencia (kW)']) + \
                                          (f['Días'] * c_pot2 * f['Potencia (kW)']) + \
                                          (f['Consumo Punta (kWh)'] * d_punta) + \
                                          (f['Consumo Llano (kWh)'] * e_llano) + \
                                          (f['Consumo Valle (kWh)'] * f_valle) - \
                                          (f['Excedente (kWh)'] * g_excedente)

                    ahorro_total = total_pagado_real - coste_cia_total
                    ahorro_anual = (ahorro_total / total_dias) * 365 if total_dias > 0 else 0

                    resumen_comparativo.append({
                        "Compañía/Tarifa": nombre_cia,
                        "Coste Total Facturas (€)": round(coste_cia_total, 2),
                        "Ahorro Total (€)": round(ahorro_total, 2),
                        "Ahorro Anual Est. (€)": round(ahorro_anual, 2)
                    })
                except: continue

            df_final = pd.DataFrame(resumen_comparativo).sort_values(by="Coste Total Facturas (€)")

            # --- INTERFAZ DE RESULTADOS ---
            st.subheader(f"📊 Resultado para un periodo de {total_dias} días ({len(datos_facturas)} facturas)")
            
            st.table(df_final) # Tabla comparativa simple y directa

            # Resaltar la mejor opción
            mejor_opcion = df_final[df_final["Ahorro Total (€)"] > 0].iloc[0] if not df_final[df_final["Ahorro Total (€)"] > 0].empty else None
            
            if mejor_opcion is not None:
                st.success(f"🏆 La mejor opción es **{mejor_opcion['Compañía/Tarifa']}**. "
                           f"Habrías ahorrado **{mejor_opcion['Ahorro Total (€)']} €** en este periodo.")
                st.info(f"📈 Proyección: El ahorro anual estimado con esta compañía es de **{mejor_opcion['Ahorro Anual Est. (€)']} €**.")
