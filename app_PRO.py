
import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os
from fpdf import FPDF

def generar_pdf_resumen(datos_factura, mejor_opcion):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Resumen de Analisis Energetico", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "Datos de la Factura Analizada:", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, f"- Fecha: {datos_factura['Fecha']}", ln=True)
    pdf.cell(200, 10, f"- Dias de consumo: {datos_factura['Días']}", ln=True)
    pdf.cell(200, 10, f"- Potencia Contratada: {datos_factura['Potencia (kW)']} kW", ln=True)
    pdf.cell(200, 10, f"- Total Factura Actual: {datos_factura['Total Real']} EUR", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "Mejor Alternativa Encontrada:", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, f"- Compania: {mejor_opcion['Compañía/Tarifa']}", ln=True)
    pdf.cell(200, 10, f"- Coste Estimado: {mejor_opcion['Coste (€)']} EUR", ln=True)
    pdf.cell(200, 10, f"- Ahorro en esta factura: {mejor_opcion['Ahorro']} EUR", ln=True)
    
    # Cálculo de ahorro anual estimado (proporcional a 365 días)
    ahorro_anual = round((mejor_opcion['Ahorro'] / datos_factura['Días']) * 365, 2) if datos_factura['Días'] > 0 else 0
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(0, 128, 0)
    pdf.cell(200, 10, f"AHORRO ANUAL ESTIMADO: {ahorro_anual} EUR", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

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
        match_potencia = re.search(r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        match_fecha = re.search(r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})', texto_completo, re.IGNORECASE)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"
        match_dias = re.search(r'(\d+)\s*días', texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        match_excedente = re.search(r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
        match_total = re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {"Fecha": fecha, "Días": dias, "Potencia (kW)": potencia, "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'], "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente, "Total Real": total_real}

st.set_page_config(page_title="Comparador Energetico", layout="wide")
st.title("⚡ Comparador de Facturas Electricas Pro")

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
                st.error(f"Error procesando {uploaded_file.name}: {e}")

        if datos_facturas:
            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0})
                for index, tarifa in df_tarifas.iterrows():
                    try:
                        coste_estimado = (fact['Días'] * pd.to_numeric(tarifa.iloc[1]) * fact['Potencia (kW)']) + (fact['Días'] * pd.to_numeric(tarifa.iloc[2]) * fact['Potencia (kW)']) + (fact['Consumo Punta (kWh)'] * pd.to_numeric(tarifa.iloc[3])) + (fact['Consumo Llano (kWh)'] * pd.to_numeric(tarifa.iloc[4])) + (fact['Consumo Valle (kWh)'] * pd.to_numeric(tarifa.iloc[5])) - (fact['Excedente (kWh)'] * pd.to_numeric(tarifa.iloc[6]))
                        resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": tarifa.iloc[0], "Coste (€)": round(coste_estimado, 2), "Ahorro": round(fact['Total Real'] - coste_estimado, 2)})
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).sort_values(by=["Mes/Fecha", "Coste (€)"])
            st.subheader("📊 Comparativa de Mercado")
            st.dataframe(df_comp, hide_index=True, use_container_width=True)

            mejor = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].iloc[0]
            if mejor["Ahorro"] > 0:
                # Mostrar Ahorro Anual Estimado en la UI 
                ahorro_anual = round((mejor['Ahorro'] / df_resumen_pdfs.iloc[0]['Días']) * 365, 2)
                st.success(f"💡 Ahorro en esta factura: {mejor['Ahorro']} € | **AHORRO ANUAL ESTIMADO: {ahorro_anual} €**")
                
                # Botón de descarga del PDF Resumen
                pdf_data = generar_pdf_resumen(df_resumen_pdfs.iloc[0], mejor)
                st.download_button(label="📥 Descargar PDF Resumen", data=pdf_data, file_name="resumen_ahorro.pdf", mime="application/pdf")
