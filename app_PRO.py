
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

st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}' en el repositorio.")
else:
    uploaded_files = st.file_uploader("Sube tus facturas PDF (puedes subir varias)", type="pdf", accept_multiple_files=True)

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
            
            # Cálculo de resultados
            resultados_finales = []
            for _, fact in df_resumen_pdfs.iterrows():
                # Añadir la factura actual del usuario
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'],
                    "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'],
                    "Ahorro": 0.0,
                    "Días": fact['Días']
                })

                for _, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        b_pot1, c_pot2 = pd.to_numeric(tarifa.iloc[1]), pd.to_numeric(tarifa.iloc[2])
                        d_punta, e_llano, f_valle = pd.to_numeric(tarifa.iloc[3]), pd.to_numeric(tarifa.iloc[4]), pd.to_numeric(tarifa.iloc[5])
                        g_excedente = pd.to_numeric(tarifa.iloc[6])

                        coste_estimado = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + \
                                         (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + \
                                         (fact['Consumo Punta (kWh)'] * d_punta) + \
                                         (fact['Consumo Llano (kWh)'] * e_llano) + \
                                         (fact['Consumo Valle (kWh)'] * f_valle) - \
                                         (fact['Excedente (kWh)'] * g_excedente)
                        
                        ahorro = fact['Total Real'] - coste_estimado
                        resultados_finales.append({
                            "Mes/Fecha": fact['Fecha'],
                            "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste_estimado, 2),
                            "Ahorro": round(ahorro, 2),
                            "Días": fact['Días']
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales)

            # --- TABLA RESUMEN AGREGADA (POR COMPAÑÍA) ---
            st.subheader("📋 Resumen Total Acumulado")
            # Agrupamos por compañía para ver el ahorro total de todas las facturas subidas
            resumen_agrupado = df_comp.groupby("Compañía/Tarifa").agg({
                "Coste (€)": "sum",
                "Ahorro": "sum",
                "Días": "sum"
            }).reset_index().sort_values("Coste (€)")

            st.dataframe(resumen_agrupado[["Compañía/Tarifa", "Coste (€)", "Ahorro"]], use_container_width=True, hide_index=True)

            # --- LÓGICA DE AHORRO Y ESTIMACIÓN ANUAL ---
            mejor_opcion = resumen_agrupado[resumen_agrupado["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].iloc[0]
            
            if mejor_opcion["Ahorro"] > 0:
                dias_totales = mejor_opcion["Días"]
                ahorro_total = mejor_opcion["Ahorro"]
                # Proyección anual: (Ahorro total / Días totales analizados) * 365
                estimado_anual = (ahorro_total / dias_totales) * 365 if dias_totales > 0 else 0
                
                st.success(f"💡 **Oportunidad Detectada:** Con la compañía **{mejor_opcion['Compañía/Tarifa']}** habrías ahorrado un total de **{round(ahorro_total, 2)} €** en las facturas subidas.")
                st.metric(label="Ahorro Estimado Anual (Proyección)", value=f"{round(estimado_anual, 2)} €")
            else:
                st.info("✅ Tus facturas actuales parecen estar en la mejor tarifa disponible.")

            # --- BOTÓN PARA MOSTRAR TABLA DETALLADA ---
            if st.button("Ver desglose detallado por factura"):
                st.subheader("🔍 Detalle por Período y Factura")
                st.dataframe(
                    df_comp.sort_values(["Mes/Fecha", "Coste (€)"]),
                    column_config={
                        "Coste (€)": st.column_config.NumberColumn("Coste en Período", format="%.2f €"),
                        "Ahorro": st.column_config.NumberColumn("Ahorro en Período", format="%.2f €")
                    },
                    use_container_width=True,
                    hide_index=True
                )
