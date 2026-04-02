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
    excedente = 0.0
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        if match_cons:
            consumos['punta'] = float(match_cons.group(1).replace(',', '.'))
            consumos['llano'] = float(match_cons.group(2).replace(',', '.'))
            consumos['valle'] = float(match_cons.group(3).replace(',', '.'))
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

    elif es_octopus:
        compania = "Octopus Energy"
        m_fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'\((\d+)\s+días\)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_punta = re.search(r'Punta\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Llano\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Valle\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_val_pot = re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_val_ene = re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0) + \
                     (float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0)
        m_exc = re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = float(m_exc.group(1).replace(',', '.')) if m_exc else 0.0

    elif es_naturgy:
        compania = "Naturgy"
        m_fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'Financiación\s+de\s+Bono\s+Social\s+(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'Potencia\s+contratada\s+P1:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_punta = re.search(r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_val_pot = re.search(r'Importe\s+potencia\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_val_ene = re.search(r'Importe\s+energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0) + \
                     (float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0)
        m_exc = re.search(r'Valoración\s+excedentes\s*(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(m_exc.group(1).replace(',', '.'))) if m_exc else 0.0

    elif es_xxi or es_endesa_luz:
        compania = "Energía XXI" if es_xxi else "Endesa Energía"
        # Fecha de emisión con soporte para múltiples formatos
        m_fecha = re.search(r'(?:Fecha\s+emisión\s+factura|Fecha\s+de\s+emisión):\s*([\d/]{8,10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        # Potencia con soporte para saltos de línea y prefijos
        m_pot = re.search(r'Potencia\s+contratada.*?\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE | re.DOTALL)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        
        m_dias = re.search(r'(\d+)\s*días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        # Consumos P1, P2, P3
        pats = {'punta': r'P1:?\s*([\d,.]+)\s*kWh', 'llano': r'P2:?\s*([\d,.]+)\s*kWh', 'valle': r'P3:?\s*([\d,.]+)\s*kWh'}
        for k, p in pats.items():
            m = re.search(p, texto_completo, re.IGNORECASE)
            if m: consumos[k] = float(m.group(1).replace(',', '.'))

        # Suma de Término Fijo + Variable
        m_fijo = re.search(r'(?:Por\s+potencia\s+contratada|Potencia\s+facturada).*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE | re.DOTALL)
        m_var = re.search(r'(?:Por\s+energía\s+consumida|Energía\s+facturada).*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE | re.DOTALL)
        total_real = (float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0) + \
                     (float(m_var.group(1).replace(',', '.')) if m_var else 0.0)

    elif es_iberdrola:
        compania = "Iberdrola"
        m_pot = re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_per = re.search(r'(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo)
        fecha = m_per.group(2) if m_per else "No encontrada"
        m_imp_pot = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_imp_ene = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_imp_pot.group(1).replace(',', '.')) if m_imp_pot else 0.0) + \
                     (float(m_imp_ene.group(1).replace(',', '.')) if m_imp_ene else 0.0)

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- CÓDIGO INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Energetika - Comparador Pro", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"Error: No se encuentra el archivo '{excel_path}'.")
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
            df_resumen = pd.DataFrame(datos_facturas)
            with st.expander("🔍 Revisar datos extraídos", expanded=True):
                df_resumen = st.data_editor(df_resumen, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen.iterrows():
                # Añadir la factura original como referencia
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Dias_Factura": fact['Días']
                })

                for _, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        p1, p2 = pd.to_numeric(tarifa.iloc[1]), pd.to_numeric(tarifa.iloc[2])
                        ep, el, ev = pd.to_numeric(tarifa.iloc[3]), pd.to_numeric(tarifa.iloc[4]), pd.to_numeric(tarifa.iloc[5])
                        exc_val = pd.to_numeric(tarifa.iloc[6])

                        coste = (fact['Días'] * p1 * fact['Potencia (kW)']) + \
                                (fact['Días'] * p2 * fact['Potencia (kW)']) + \
                                (fact['Consumo Punta (kWh)'] * ep) + \
                                (fact['Consumo Llano (kWh)'] * el) + \
                                (fact['Consumo Valle (kWh)'] * ev) - \
                                (fact['Excedente (kWh)'] * exc_val)
                        
                        resultados_finales.append({
                            "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2),
                            "Dias_Factura": fact['Días'], "p1": p1, "p2": p2, "ep": ep, "el": el, "ev": ev, "exc": exc_val
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            
            # Ranking y Descarga
            ranking = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].groupby("Compañía/Tarifa")["Ahorro"].sum().sort_values(ascending=False).reset_index()
            
            st.divider()
            if not ranking.empty:
                st.subheader(f"🏆 Mejor opción: {ranking.iloc[0]['Compañía/Tarifa']}")
                st.metric("Ahorro Total", f"{round(ranking.iloc[0]['Ahorro'], 2)} €")

            st.dataframe(df_comp.drop(columns=['p1','p2','ep','el','ev','exc'], errors='ignore'), use_container_width=True, hide_index=True)

            # Exportación Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Comparativa')
                ranking.to_excel(writer, index=False, sheet_name='Ranking')
            
            st.download_button("📥 Descargar Informe", buffer.getvalue(), "estudio_energetika.xlsx", "application/vnd.ms-excel", use_container_width=True)
