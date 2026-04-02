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
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
    potencia = 0.0
    fecha = "No encontrada"
    dias = 0
    total_real = 0.0
    excedente = 0.0

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        if match_cons:
            consumos['punta'] = float(match_cons.group(1).replace(',', '.'))
            consumos['llano'] = float(match_cons.group(2).replace(',', '.'))
            consumos['valle'] = float(match_cons.group(3).replace(',', '.'))
        m_pot = re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_fec = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo)
        fecha = m_fec.group(1) if m_fec else "No encontrada"
        m_dias = re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_tot = re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo)
        total_real = float(m_tot.group(1).replace(',', '.')) if m_tot else 0.0

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
        total_real = (float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0) + (float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0)
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
        m_subtotal = re.search(r'Subtotal\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = float(m_subtotal.group(1).replace(',', '.')) if m_subtotal else 0.0

    elif es_xxi or es_endesa_luz:
        compania = "Energía XXI" if es_xxi else "Endesa Energía"
        # Fecha con soporte para texto y barras
        m_fec = re.search(r'(?:Fecha\s+de\s+emisión:|emitida\s+el)\s*([\d/]+(?:\s+de\s+\w+\s+de\s+\d+)?|[\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fec.group(1) if m_fec else "No encontrada"
        
        m_dias = re.search(r'(\d+)\s*días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        # Potencia más flexible
        m_pot = re.search(r'Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        
        patrones_consumo = {
            'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Punta\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)'],
            'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Llano\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)'],
            'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Valle\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)']
        }
        for tramo, pats in patrones_consumo.items():
            for p in pats:
                m = re.search(p, texto_completo, re.IGNORECASE)
                if m:
                    consumos[tramo] = float(m.group(1).replace(',', '.'))
                    break

        m_total = re.search(r'Total\s+electricidad\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = float(m_total.group(1).replace(',', '.')) if m_total else 0.0

    elif es_iberdrola:
        compania = "Iberdrola"
        m_pot = re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_per = re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = m_per.group(2) if m_per else "No encontrada"
        m_p = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_l = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_v = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {'punta': float(m_p.group(1).replace(',', '.')) if m_p else 0.0, 'llano': float(m_l.group(1).replace(',', '.')) if m_l else 0.0, 'valle': float(m_v.group(1).replace(',', '.')) if m_v else 0.0}
        m_itot = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_etot = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_itot.group(1).replace(',', '.')) if m_itot else 0.0) + (float(m_etot.group(1).replace(',', '.')) if m_etot else 0.0)

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- Código Streamlit ---
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
            cols = ["Compañía", "Fecha", "Días", "Potencia (kW)", "Consumo Punta (kWh)", "Consumo Llano (kWh)", "Consumo Valle (kWh)", "Excedente (kWh)", "Total Real", "Archivo"]
            df_resumen_pdfs = df_resumen_pdfs[cols]

            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []
            
            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": f"📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Dias_Factura": fact['Días']
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
                            "Coste (€)": round(coste_estimado, 2), "Ahorro": round(ahorro, 2),
                            "Dias_Factura": fact['Días'],
                            "p1": b_pot1, "p2": c_pot2, "ep": d_punta, "el": e_llano, "ev": f_valle, "exc": g_excedente
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            
            df_solo_ofertas = df_comp[~df_comp["Compañía/Tarifa"].str.contains("📍 TU FACTURA")]
            ranking_total = df_solo_ofertas.groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index().sort_values(by="Ahorro", ascending=False)

            if not ranking_total.empty:
                ganador_nombre = ranking_total.iloc[0]['Compañía/Tarifa']
                fila_ganador = df_solo_ofertas[df_solo_ofertas["Compañía/Tarifa"] == ganador_nombre].iloc[0]
                df_ganadora = pd.DataFrame([
                    {"Concepto": "Compañía Ganadora", "Valor": ganador_nombre},
                    {"Concepto": "P1 Potencia (€/kW/día)", "Valor": fila_ganador["p1"]},
                    {"Concepto": "P2 Potencia (€/kW/día)", "Valor": fila_ganador["p2"]},
                    {"Concepto": "Energía Punta (€/kWh)", "Valor": fila_ganador["ep"]},
                    {"Concepto": "Energía Llano (€/kWh)", "Valor": fila_ganador["el"]},
                    {"Concepto": "Energía Valle (€/kWh)", "Valor": fila_ganador["ev"]},
                    {"Concepto": "Excedente (€/kWh)", "Valor": fila_ganador["exc"]}
                ])

                st.divider()
                st.subheader("🏆 Resultado del Análisis")
                c1, c2 = st.columns(2)
                with c1: st.success(f"La mejor compañía es: **{ganador_nombre}**")
                with c2: st.metric(label="Ahorro Total Acumulado", value=f"{round(ranking_total.iloc[0]['Ahorro'], 2)} €")

                st.subheader("📊 Comparativa Detallada")
                st.dataframe(df_comp.drop(columns=['p1','p2','ep','el','ev','exc'], errors='ignore'), use_container_width=True, hide_index=True)

                buffer_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    df_comp.drop(columns=['p1','p2','ep','el','ev','exc'], errors='ignore').to_excel(writer, index=False, sheet_name='Detalle')
                    ranking_total.to_excel(writer, index=False, sheet_name='Ranking')
                    df_resumen_pdfs.drop(columns=["Compañía"], errors='ignore').to_excel(writer, index=False, sheet_name='Originales')
                    df_ganadora.to_excel(writer, index=False, sheet_name='Tarifa Ganadora')

                st.download_button(label="📥 Descargar Informe", data=buffer_excel.getvalue(), file_name="estudio_ahorro.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
