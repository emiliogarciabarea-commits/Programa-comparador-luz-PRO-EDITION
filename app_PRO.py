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
                lineas_factura.extend([l.strip() for l in texto_pag.split('\n') if l.strip()])

    # --- DETECCIÓN DE COMPAÑÍA ---
    es_endesa = re.search(r'endesa\s+luz|energía\s+xxi|comercializadora\s+de\s+referencia', texto_completo, re.IGNORECASE)
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)

    if es_endesa:
        # --- LÓGICA ULTRA-REFORZADA PARA ENDESA ---
        # 1. FECHA: Captura la primera fecha con formato estándar en todo el documento
        todas_las_fechas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto_completo)
        fecha = todas_las_fechas[0] if todas_las_fechas else "No encontrada"

        # 2. DÍAS: Busca el número que precede a la palabra días
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        # 3. POTENCIA: Busca el valor en kW (normalmente P1)
        m_pot = re.search(r'([\d,.]+)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        # 4. CONSUMOS: Captura los valores kWh en orden (Punta, Llano, Valle)
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        matches_kwh = re.findall(r'([\d,.]+)\s*kWh', texto_completo)
        if len(matches_kwh) >= 3:
            consumos['punta'] = float(matches_kwh[0].replace(',', '.'))
            consumos['llano'] = float(matches_kwh[1].replace(',', '.'))
            consumos['valle'] = float(matches_kwh[2].replace(',', '.'))
        elif len(matches_kwh) == 1:
            consumos['punta'] = float(matches_kwh[0].replace(',', '.'))

        # 5. TOTAL REAL: Suma de conceptos para evitar errores de lectura del total pie de página
        v_pot = 0.0
        v_ene = 0.0
        for linea in lineas_factura:
            if "Potencia" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: v_pot = float(m.group(1).replace(',', '.'))
            if "Energía" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: v_ene = float(m.group(1).replace(',', '.'))
        total_real = v_pot + v_ene
        excedente = 0.0

    elif es_el_corte_ingles:
        match_cons = re.search(r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)', texto_completo)
        consumos = {'punta': float(match_cons.group(1).replace(',', '.')) if match_cons else 0.0, 'llano': float(match_cons.group(2).replace(',', '.')) if match_cons else 0.0, 'valle': float(match_cons.group(3).replace(',', '.')) if match_cons else 0.0}
        potencia = float(re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo) else 0.0
        fecha = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo).group(1)) if re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo) else 0
        total_real = float(re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo).group(1).replace(',', '.')) if re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo) else 0.0
        excedente = 0.0 

    elif es_repsol:
        fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE) else "No encontrada"
        potencia = float(re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        dias = int(re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE).group(1)) if re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE) else 0
        v_fijo = float(re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        v_ener = float(re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        total_real = v_fijo + v_ener
        valor_cons = float(re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        consumos = {'punta': valor_cons, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        potencia = float(re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        dias = int(re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL).group(1)) if re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL) else 0
        fecha = re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL).group(2) if re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL) else "No encontrada"
        consumos = {'punta': float(re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo) else 0.0, 'llano': float(re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo) else 0.0, 'valle': float(re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo) else 0.0}
        total_real = (float(re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0) + (float(re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0)
        excedente = 0.0

    else:
        # Lógica genérica
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        for tramo, patrones in {'punta': [r'P1:?\s*([\d,.]+)\s*kWh', r'Punta\s*([\d,.]+)\s*kWh'], 'llano': [r'P2:?\s*([\d,.]+)\s*kWh', r'Llano\s*([\d,.]+)\s*kWh'], 'valle': [r'P3:?\s*([\d,.]+)\s*kWh', r'Valle\s*([\d,.]+)\s*kWh']}.items():
            for p in patrones:
                m = re.search(p, texto_completo, re.IGNORECASE)
                if m: consumos[tramo] = float(m.group(1).replace(',', '.')); break
        potencia = float(re.search(r'Potencia.*?([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia.*?([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        fecha = re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo) else "No encontrada"
        dias = int(re.search(r'(\d+)\s*días', texto_completo).group(1)) if re.search(r'(\d+)\s*días', texto_completo) else 0
        excedente = abs(float(re.search(r'excedentes.*?(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.'))) if re.search(r'excedentes.*?(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        total_real = float(re.search(r'(?:Total|Importe)\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'(?:Total|Importe)\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Comparador Energético Pro", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas")

excel_path = "tarifas_companias.xlsx"
if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}'.")
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
            with st.expander("🔍 Revisar Datos Extraídos"):
                df_resumen = st.data_editor(df_resumen, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados = []
            for _, fact in df_resumen.iterrows():
                # Fila de referencia (actual)
                resultados.append({"Mes/Fecha": fact['Fecha'], "Compañía": "📍 ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0})
                # Cálculo comparativo
                for _, t in df_tarifas.iterrows():
                    try:
                        coste = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + (fact['Consumo Punta (kWh)'] * t.iloc[3]) + (fact['Consumo Llano (kWh)'] * t.iloc[4]) + (fact['Consumo Valle (kWh)'] * t.iloc[5]) - (fact['Excedente (kWh)'] * t.iloc[6])
                        resultados.append({"Mes/Fecha": fact['Fecha'], "Compañía": t.iloc[0], "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2)})
                    except: continue

            st.subheader("📊 Comparativa")
            st.dataframe(pd.DataFrame(resultados).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False]), use_container_width=True, hide_index=True)
