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
    
    # Identificación específica de Endesa Luz (Mercado Libre)
    es_endesa_luz = (re.search(r'Endesa\s+Energía\s+S\.A', texto_completo, re.IGNORECASE) or \
                    re.search(r'endesa\s+luz', texto_completo, re.IGNORECASE)) and \
                    not re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)

    if es_el_corte_ingles:
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

    elif es_endesa_luz:
        # --- LÓGICA ENDESA LUZ ---
        # 1. Fecha: Captura la primera fecha (emisión)
        fechas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto_completo)
        fecha = fechas[0] if fechas else "No encontrada"

        # 2. Potencia: Captura el valor numérico justo antes de "kW" (ej: 2,000 kW)
        # Limpiamos posibles puntos de miles para evitar el error de float
        m_pot = re.search(r'([\d,.]+)\s*kW', texto_completo)
        if m_pot:
            val_pot = m_pot.group(1).replace('.', '').replace(',', '.')
            potencia = float(val_pot)
        else:
            potencia = 0.0

        # 3. Días: Captura el número antes de "días"
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        # 4. Consumos: P1, P2, P3 en orden kWh
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        vals_kwh = re.findall(r'([\d,.]+)\s*kWh', texto_completo)
        if len(vals_kwh) >= 3:
            consumos['punta'] = float(vals_kwh[0].replace(',', '.'))
            consumos['llano'] = float(vals_kwh[1].replace(',', '.'))
            consumos['valle'] = float(vals_kwh[2].replace(',', '.'))
        elif len(vals_kwh) == 1:
            consumos['punta'] = float(vals_kwh[0].replace(',', '.'))

        # 5. Total Factura
        m_total = re.search(r'Total\s+importe\s+factura\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        if m_total:
            total_real = float(m_total.group(1).replace(',', '.'))
        else:
            m_total_alt = re.findall(r'([\d,.]+)\s*€', texto_completo)
            total_real = float(m_total_alt[-1].replace(',', '.')) if m_total_alt else 0.0
        excedente = 0.0

    elif es_repsol:
        fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE) else "No encontrada"
        potencia = float(re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        dias = int(re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE).group(1)) if re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE) else 0
        v_fijo = float(re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        v_ener = float(re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        total_real = v_fijo + v_ener
        consumos = {'punta': float(re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        potencia = float(re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        dias = int(re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL).group(1)) if re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL) else 0
        fecha = re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL).group(2) if re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL) else "No encontrada"
        consumos = {
            'punta': float(re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo) else 0.0,
            'llano': float(re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo) else 0.0,
            'valle': float(re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo) else 0.0
        }
        total_real = (float(re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0) + \
                     (float(re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0)
        excedente = 0.0

    else:
        # Lógica genérica
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        for tramo, patrones in {'punta': [r'P1:?\s*([\d,.]+)\s*kWh', r'Punta\s*([\d,.]+)\s*kWh'], 'llano': [r'P2:?\s*([\d,.]+)\s*kWh', r'Llano\s*([\d,.]+)\s*kWh'], 'valle': [r'P3:?\s*([\d,.]+)\s*kWh', r'Valle\s*([\d,.]+)\s*kWh']}.items():
            for p in patrones:
                m = re.search(p, texto_completo, re.IGNORECASE)
                if m: consumos[tramo] = float(m.group(1).replace(',', '.')); break
        
        potencia = float(re.search(r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        fecha = re.search(r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})', texto_completo, re.IGNORECASE).group(1) if re.search(r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})', texto_completo, re.IGNORECASE) else "No encontrada"
        
        if es_naturgy:
            dias = int(re.search(r'Término\s+potencia\s+P1.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL).group(1)) if re.search(r'Término\s+potencia\s+P1.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL) else 0
        else:
            dias = int(re.search(r'(\d+)\s*días', texto_completo).group(1)) if re.search(r'(\d+)\s*días', texto_completo) else 0

        excedente = abs(float(re.search(r'excedentes.*?(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.'))) if re.search(r'excedentes.*?(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        
        es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)
        if es_xxi:
            m_pot_val = re.search(r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            m_ene_val = re.search(r'por\s+energía\s+consumida\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = (float(m_pot_val.group(1).replace(',', '.')) if m_pot_val else 0.0) + (float(m_ene_val.group(1).replace(',', '.')) if m_ene_val else 0.0)
        else:
            total_real = float(re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- STREAMLIT UI ---
st.set_page_config(page_title="Comparador Energético Pro", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

excel_path = "tarifas_companias.xlsx"
if not os.path.exists(excel_path):
    st.error(f"No se encuentra '{excel_path}'.")
else:
    uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)
    if uploaded_files:
        datos_facturas = []
        for f in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(f.read()))
                res['Archivo'] = f.name
                datos_facturas.append(res)
            except Exception as e:
                st.error(f"Error procesando {f.name}: {e}")

        if datos_facturas:
            df_resumen = pd.DataFrame(datos_facturas)
            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen = st.data_editor(df_resumen, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados = []
            for _, fact in df_resumen.iterrows():
                resultados.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Dias": fact['Días']})
                for _, t in df_tarifas.iterrows():
                    try:
                        c = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + (fact['Consumo Punta (kWh)'] * t.iloc[3]) + (fact['Consumo Llano (kWh)'] * t.iloc[4]) + (fact['Consumo Valle (kWh)'] * t.iloc[5]) - (fact['Excedente (kWh)'] * t.iloc[6])
                        resultados.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": t.iloc[0], "Coste (€)": round(c, 2), "Ahorro": round(fact['Total Real'] - c, 2), "Dias": fact['Días']})
                    except: continue

            df_comp = pd.DataFrame(resultados).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            st.subheader("📊 Comparativa Detallada")
            st.dataframe(df_comp, use_container_width=True, hide_index=True)

            # Botón de descarga
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Comparativa')
            st.download_button(label="📥 Descargar Informe", data=buffer.getvalue(), file_name="estudio_ahorro.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
