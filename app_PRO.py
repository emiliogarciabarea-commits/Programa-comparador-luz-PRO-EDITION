import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    lineas_factura = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_pag = pagina.extract_text()
            if texto_pag:
                texto_completo += texto_pag + "\n"
                lineas_factura.extend(texto_pag.split('\n'))

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    # Identificación específica solicitada
    es_endesa = re.search(r'endesa\s+luz', texto_completo, re.IGNORECASE)

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
        m_consumo_gen = re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        valor_consumo = float(m_consumo_gen.group(1).replace(',', '.')) if m_consumo_gen else 0.0
        consumos = {'punta': valor_consumo, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        m_pot = re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_per = re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = m_per.group(2) if m_per else "No encontrada"
        m_punta = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_llano = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_valle = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_i_pot = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_i_ene = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_i_pot.group(1).replace(',', '.')) if m_i_pot else 0.0) + (float(m_i_ene.group(1).replace(',', '.')) if m_i_ene else 0.0)
        excedente = 0.0

    elif es_endesa:
        # Lógica optimizada para las capturas de Endesa
        m_fecha = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        m_dias = re.search(r'periodo\s+de\s+facturacion:.*?\((\d+)\s+días\)', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        potencia = 0.0
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        v_pot, v_ene = 0.0, 0.0

        for linea in lineas_factura:
            # Potencia P1 (Ej: "4,400 kW")
            if "kW" in linea and not potencia:
                m = re.search(r'([\d,.]+)\s*kW', linea)
                if m: potencia = float(m.group(1).replace(',', '.'))
            
            # Consumos (Punta, Llano, Valle)
            if "Punta" in linea and "kWh" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['punta'] = float(m.group(1).replace(',', '.'))
            elif "Llano" in linea and "kWh" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['llano'] = float(m.group(1).replace(',', '.'))
            elif "Valle" in linea and "kWh" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['valle'] = float(m.group(1).replace(',', '.'))
                
            # Importes del resumen (con puntos suspensivos)
            if "Potencia" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: v_pot = float(m.group(1).replace(',', '.'))
            if "Energia" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: v_ene = float(m.group(1).replace(',', '.'))

        total_real = v_pot + v_ene
        excedente = 0.0

    else:
        # Lógica genérica y Naturgy
        patrones_consumo = {
            'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh']
        }
        consumos = {t: 0.0 for t in patrones_consumo}
        for tramo, patrones in patrones_consumo.items():
            for p in patrones:
                m = re.search(p, texto_completo, re.IGNORECASE)
                if m:
                    consumos[tramo] = float(m.group(1).replace(',', '.'))
                    break
        m_pot = re.search(r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_fecha = re.search(r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        if es_naturgy:
            m_d = re.search(r'Término\s+potencia\s+P1.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
            dias = int(m_d.group(1)) if m_d else 0
        else:
            m_d = re.search(r'(\d+)\s*días', texto_completo)
            dias = int(m_d.group(1)) if m_d else 0
            
        m_exc = re.search(r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(m_exc.group(1).replace(',', '.'))) if m_exc else 0.0
        total_real = float(re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0

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
    st.error(f"No se encuentra el archivo '{excel_path}'")
else:
    uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)
    if uploaded_files:
        datos_facturas = []
        for f in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(f.read()))
                res['Archivo'] = f.name
                datos_facturas.append(res)
            except Exception as e: st.error(f"Error en {f.name}: {e}")

        if datos_facturas:
            df_resumen = st.data_editor(pd.DataFrame(datos_facturas), use_container_width=True, hide_index=True)
            df_tarifas = pd.read_excel(excel_path)
            res_final = []

            for _, fact in df_resumen.iterrows():
                res_final.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Dias": fact['Días']})
                for _, t in df_tarifas.iterrows():
                    try:
                        coste = (fact['Días'] * (t.iloc[1]+t.iloc[2]) * fact['Potencia (kW)']) + \
                                (fact['Consumo Punta (kWh)'] * t.iloc[3]) + \
                                (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                                (fact['Consumo Valle (kWh)'] * t.iloc[5]) - (fact['Excedente (kWh)'] * t.iloc[6])
                        res_final.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": t.iloc[0], "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2), "Dias": fact['Días']})
                    except: continue
            
            df_comp = pd.DataFrame(res_final).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            st.subheader("📊 Comparativa")
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
