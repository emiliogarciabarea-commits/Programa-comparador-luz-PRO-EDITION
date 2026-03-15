import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os
import plotly.express as px
from fpdf import FPDF

# --- FUNCIONES DE EXTRACCIÓN Y PDF (Mantenidas y mejoradas) ---
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
        consumos = {t: 0.0 for t in patrones_consumo}
        for tramo, patrones in patrones_consumo.items():
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

    return {"Fecha": fecha, "Días": dias, "Potencia (kW)": potencia, "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'], "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente, "Total Real": total_real}

def generar_pdf(resumen_df, mejor_opcion, ahorro_anual):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Informe de Comparativa Energetica", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Resumen de Ahorro Acumulado:", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(80, 10, "Compania/Tarifa", 1)
    pdf.cell(50, 10, "Coste Total (E)", 1)
    pdf.cell(50, 10, "Ahorro Total (E)", 1)
    pdf.ln()
    for _, row in resumen_df.iterrows():
        pdf.cell(80, 10, str(row['Compañía/Tarifa'])[:35], 1)
        pdf.cell(50, 10, f"{row['Coste (€)']:.2f}", 1)
        pdf.cell(50, 10, f"{row['Ahorro']:.2f}", 1)
        pdf.ln()
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=f"RECOMENDACION: {mejor_opcion['Compañía/Tarifa']}", ln=True)
    pdf.cell(0, 10, txt=f"AHORRO ANUAL ESTIMADO: {ahorro_anual:.2f} E", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- CONFIGURACIÓN UI ---
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
            df_tarifas = pd.read_excel(excel_path)
            
            resultados_finales = []
            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Días": fact['Días']})

                for _, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        b_pot1, c_pot2 = pd.to_numeric(tarifa.iloc[1]), pd.to_numeric(tarifa.iloc[2])
                        d_p, e_l, f_v = pd.to_numeric(tarifa.iloc[3]), pd.to_numeric(tarifa.iloc[4]), pd.to_numeric(tarifa.iloc[5])
                        g_exc = pd.to_numeric(tarifa.iloc[6])

                        coste = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + \
                                (fact['Consumo Punta (kWh)'] * d_p) + (fact['Consumo Llano (kWh)'] * e_l) + \
                                (fact['Consumo Valle (kWh)'] * f_v) - (fact['Excedente (kWh)'] * g_exc)
                        
                        resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia, "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2), "Días": fact['Días']})
                    except: continue

            df_comp = pd.DataFrame(resultados_finales)
            resumen_agrupado = df_comp.groupby("Compañía/Tarifa").agg({"Coste (€)": "sum", "Ahorro": "sum", "Días": "sum"}).reset_index().sort_values("Coste (€)")

            # --- GRÁFICA DE BARRAS CON COLORES ---
            st.subheader("📊 Comparativa de Ahorro Total")
            
            # Filtramos la factura actual para la gráfica para que la comparativa sea clara
            df_grafica = resumen_agrupado[resumen_agrupado["Compañía/Tarifa"] != "📍 TU ACTUAL"].copy()
            # Asignar colores: Verde si ahorro > 0, Rojo si ahorro <= 0
            df_grafica['Color'] = df_grafica['Ahorro'].apply(lambda x: 'Ahorro (Verde)' if x > 0 else 'Sobrecoste (Rojo)')
            
            fig = px.bar(df_grafica, 
                         x='Compañía/Tarifa', 
                         y='Ahorro',
                         color='Color',
                         color_discrete_map={'Ahorro (Verde)': '#2ecc71', 'Sobrecoste (Rojo)': '#e74c3c'},
                         title="Ahorro total acumulado por compañía (Comparado con tu tarifa actual)",
                         labels={'Ahorro': 'Ahorro Total (€)'})
            
            fig.update_layout(showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

            # --- TABLA Y MÉTRICAS ---
            st.subheader("📋 Resumen de Costes")
            st.dataframe(resumen_agrupado[["Compañía/Tarifa", "Coste (€)", "Ahorro"]], use_container_width=True, hide_index=True)

            mejor = resumen_agrupado[resumen_agrupado["Compañía/Tarifa"] != "📍 TU ACTUAL"].iloc[0]
            if mejor["Ahorro"] > 0:
                ahorro_anual = (mejor["Ahorro"] / mejor["Días"]) * 365
                st.success(f"💡 **Mejor opción:** {mejor['Compañía/Tarifa']} con un ahorro acumulado de {round(mejor['Ahorro'], 2)} €")
                st.metric("Ahorro Anual Estimado", f"{round(ahorro_anual, 2)} €")
                
                pdf_bytes = generar_pdf(resumen_agrupado, mejor, ahorro_anual)
                st.download_button("📥 Descargar Reporte PDF", pdf_bytes, "comparativa.pdf", "application/pdf")
            
            if st.button("Ver desglose por factura"):
                st.dataframe(df_comp.sort_values(["Mes/Fecha", "Coste (€)"]), use_container_width=True, hide_index=True)
