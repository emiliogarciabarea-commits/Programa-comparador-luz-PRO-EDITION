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

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa = re.search(r'endesa\s+luz', texto_completo, re.IGNORECASE)

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

    elif es_repsol:
        fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE) else "No encontrada"
        potencia = float(re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        dias = int(re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE).group(1)) if re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE) else 0
        v_fijo = float(re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        v_ener = float(re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        total_real = v_fijo + v_ener
        valor_consumo = float(re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        consumos = {'punta': valor_consumo, 'llano': 0.0, 'valle': 0.0}
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

    elif es_endesa:
        # --- BLOQUE ENDESA: BÚSQUEDA POR PATRÓN DE FECHA PURO ---
        todas_las_fechas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto_completo)
        fecha = todas_las_fechas[0] if todas_las_fechas else "No encontrada"

        m_dias = re.search(r'\((\d+)\s+días\)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0

        potencia = 0.0
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        val_pot = 0.0
        val_ene = 0.0

        for linea in lineas_factura:
            if "P1" in linea and "kW" in linea:
                m = re.search(r'([\d,.]+)\s*kW', linea)
                if m: potencia = float(m.group(1).replace(',', '.'))
            if "Punta" in linea and "kWh" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['punta'] = float(m.group(1).replace(',', '.'))
            if "Llano" in linea and "kWh" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['llano'] = float(m.group(1).replace(',', '.'))
            if "Valle" in linea and "kWh" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['valle'] = float(m.group(1).replace(',', '.'))
            if "Potencia" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: val_pot = float(m.group(1).replace(',', '.'))
            if "Energia" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: val_ene = float(m.group(1).replace(',', '.'))

        total_real = val_pot + val_ene
        excedente = 0.0

    else:
        # Lógica genérica
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        for tramo, patrones in {'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh'], 'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh'], 'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh']}.items():
            for p in patrones:
                m = re.search(p, texto_completo, re.IGNORECASE)
                if m: consumos[tramo] = float(m.group(1).replace(',', '.')); break
        potencia = float(re.search(r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        # Fecha genérica
        todas_las_fechas = re.findall(r'(\d{2}/\d{2}/\d{2,4})', texto_completo)
        fecha = todas_las_fechas[0] if todas_las_fechas else "No encontrada"
        dias = int(re.search(r'(\d+)\s*días', texto_completo).group(1)) if re.search(r'(\d+)\s*días', texto_completo) else 0
        excedente = abs(float(re.search(r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.'))) if re.search(r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        total_real = float(re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0

    return {"Fecha": fecha, "Días": dias, "Potencia (kW)": potencia, "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'], "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente, "Total Real": round(total_real, 2)}

# El resto del código Streamlit (configuración, carga de archivos, tablas, descarga) sigue igual.
st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")
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
                st.error(f"Error procesando {uploaded_file.name}: {e}")
        if datos_facturas:
            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)
            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []
            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0})
                for index, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        b_pot1, c_pot2, d_punta, e_llano, f_valle, g_excedente = [pd.to_numeric(tarifa.iloc[i], errors='coerce') for i in range(1, 7)]
                        coste_est = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + (fact['Consumo Punta (kWh)'] * d_punta) + (fact['Consumo Llano (kWh)'] * e_llano) + (fact['Consumo Valle (kWh)'] * f_valle) - (fact['Excedente (kWh)'] * g_excedente)
                        resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia, "Coste (€)": round(coste_est, 2), "Ahorro": round(fact['Total Real'] - coste_est, 2)})
                    except: continue
            df_comp = pd.DataFrame(resultados_finales).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            st.subheader("📊 Comparativa Detallada")
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
