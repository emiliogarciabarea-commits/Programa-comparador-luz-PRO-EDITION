



import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os
from fpdf import FPDF # Asegúrate de añadir 'fpdf2' a tu requirements.txt

# --- FUNCIÓN PARA GENERAR PDF ---
def generar_reporte_pdf(df_resumen, mejor_opcion, df_tarifas):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Título
    pdf.cell(190, 10, "Reporte de Comparativa Energetica", ln=True, align="C")
    pdf.ln(10)
    
    # Resumen de Ahorro
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "1. Resumen de Ahorro Estimado", ln=True)
    pdf.set_font("Arial", "", 12)
    ahorro_mensual = mejor_opcion['Ahorro']
    ahorro_anual = ahorro_mensual * 12
    
    pdf.multi_cell(190, 10, f"Basado en tu factura actual, la mejor opcion es: {mejor_opcion['Compañía/Tarifa']}.\n"
                            f"Ahorro en esta factura: {ahorro_mensual:.2f} eur\n"
                            f"Estimacion de ahorro anual: {ahorro_anual:.2f} eur")
    pdf.ln(5)

    # Tabla de Comparativa
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "2. Tabla Comparativa (Top 5)", ln=True)
    pdf.set_font("Arial", "", 10)
    for index, row in df_resumen.head(6).iterrows():
        linea = f"{row['Compañía/Tarifa']}: {row['Coste (€)']} eur (Ahorro: {row['Ahorro']} eur)"
        pdf.cell(190, 8, linea, ln=True)
    
    pdf.ln(10)
    
    # Lista de todas las tarifas analizadas
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "3. Lista de todas las Tarifas Analizadas (Excel)", ln=True)
    pdf.set_font("Arial", "", 8)
    for tarifa in df_tarifas.iloc[:, 0].unique():
        pdf.cell(190, 6, f"- {tarifa}", ln=True)

    return pdf.output(dest='S').encode('latin-1')

# --- TU CÓDIGO DE EXTRACCIÓN (SE MANTIENE IGUAL) ---
def extraer_datos_factura(pdf_path):
    # ... (Todo tu código de extraer_datos_factura igual) ...
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
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
    total_real = 0.0
    es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)
    if es_xxi:
        patron_pot_xxi = r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€'
        patron_ene_xxi = r'por\s+energía\s+consumida\s*([\d,.]+)\s*€'
        m_pot = re.search(patron_pot_xxi, texto_completo, re.IGNORECASE)
        m_ene = re.search(patron_ene_xxi, texto_completo, re.IGNORECASE)
        val_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        val_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        total_real = val_pot + val_ene
    else:
        patron_total = r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo, re.IGNORECASE)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0
    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": total_real
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
            st.dataframe(df_comp, use_container_width=True, hide_index=True)

            # --- NUEVA SECCIÓN DE EXPORTACIÓN ---
            mejor = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                if mejor["Ahorro"] > 0:
                    st.success(f"💡 Ahorro anual estimado: **{mejor['Ahorro'] * 12:.2f} €**")
                    
                    # Generar el PDF
                    pdf_bytes = generar_reporte_pdf(df_comp, mejor, df_tarifas)
                    
                    st.download_button(
                        label="📥 Descargar Resumen en PDF",
                        data=pdf_bytes,
                        file_name="reporte_ahorro_energetico.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.info("Ya tienes la mejor tarifa.")

Cual es la parte del codigo que lee los consumos y potencia  de la factura que introduce el usurario
