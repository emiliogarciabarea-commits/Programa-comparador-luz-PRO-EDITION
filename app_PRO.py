import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def limpiar_valor_seguro(texto_sucio):
    """Limpia strings con comas, € y comillas para convertirlos en float de forma segura."""
    if not texto_sucio: return 0.0
    # Quitamos todo lo que no sea número, coma o punto
    limpio = re.sub(r'[^\d,.]', '', str(texto_sucio))
    # Cambiamos coma por punto para que Python lo entienda
    limpio = limpio.replace(',', '.')
    try:
        return float(limpio)
    except:
        return 0.0

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # Normalización para Energía XXI y casos difíciles
    # Eliminamos comillas y unimos líneas para que la fecha y los importes no se corten
    texto_normalizado = texto_completo.replace('"', '').replace('\n', ' ').replace('\r', ' ')
    texto_normalizado = ' '.join(texto_normalizado.split())

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

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        consumos = {
            'punta': limpiar_valor_seguro(match_cons.group(1)) if match_cons else 0.0,
            'llano': limpiar_valor_seguro(match_cons.group(2)) if match_cons else 0.0,
            'valle': limpiar_valor_seguro(match_cons.group(3)) if match_cons else 0.0
        }
        potencia = limpiar_valor_seguro(re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo).group(1)) if re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo) else 0.0
        fecha = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo).group(1)) if re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo) else 0
        total_real = limpiar_valor_seguro(re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo).group(1)) if re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo) else 0.0
        excedente = 0.0 

    elif es_octopus:
        compania = "Octopus Energy"
        fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'\((\d+)\s+días\)', texto_completo).group(1)) if re.search(r'\((\d+)\s+días\)', texto_completo) else 0
        potencia = limpiar_valor_seguro(re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo).group(1)) if re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo) else 0.0
        consumos = {
            'punta': limpiar_valor_seguro(re.search(r'Punta\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I).group(1)) if re.search(r'Punta\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I) else 0.0,
            'llano': limpiar_valor_seguro(re.search(r'Llano\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I).group(1)) if re.search(r'Llano\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I) else 0.0,
            'valle': limpiar_valor_seguro(re.search(r'Valle\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I).group(1)) if re.search(r'Valle\s+.*?([\d,.]+)\s*kWh', texto_completo, re.I) else 0.0
        }
        v_pot = limpiar_valor_seguro(re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.I).group(1)) if re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.I) else 0.0
        v_ene = limpiar_valor_seguro(re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.I).group(1)) if re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.I) else 0.0
        total_real = v_pot + v_ene
        excedente = limpiar_valor_seguro(re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.I).group(1)) if re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.I) else 0.0

    elif es_xxi:
        compania = "Energía XXI"
        # Fecha blindada (Usa el texto normalizado)
        m_fecha = re.search(r"emitida\s+el\s+([\d]{1,2}.*?\d{4})", texto_normalizado, re.I)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        # Días
        m_dias = re.search(r'(\d+)\s*días', texto_normalizado)
        dias = int(m_dias.group(1)) if m_dias else 0

        # Potencia kW
        m_kw = re.search(r'([\d,.]+)\s*kW', texto_normalizado)
        potencia = limpiar_valor_seguro(m_kw.group(1)) if m_kw else 0.0

        # Consumos P1, P2, P3
        consumos = {}
        for p in ['P1', 'P2', 'P3']:
            m_c = re.search(rf"{p}.*?([\d,.]+)\s*kWh", texto_normalizado, re.I)
            consumos[p.lower().replace('p1','punta').replace('p2','llano').replace('p3','valle')] = limpiar_valor_seguro(m_c.group(1)) if m_c else 0.0
        
        # Lógica de resta para el Total Real (P+E)
        m_tot = re.search(r"TOTAL\s+IMPORTE\s+FACTURA\s*([\d,.]+)\s*€", texto_normalizado, re.I)
        m_iva = re.search(r"IVA\s+normal\s*([\d,.]+)\s*€", texto_normalizado, re.I)
        m_ie = re.search(r"Impuesto\s+electricidad\s*([\d,.]+)\s*€", texto_normalizado, re.I)
        m_alq = re.search(r"Alquiler\s+del\s+contador\s*([\d,.]+)\s*€", texto_normalizado, re.I)
        m_otr = re.search(r"Otros\s*([\d,.]+)\s*€", texto_normalizado, re.I)
        
        v_tot = limpiar_valor_seguro(m_tot.group(1)) if m_tot else 0.0
        v_iva = limpiar_valor_seguro(m_iva.group(1)) if m_iva else 0.0
        v_ie = limpiar_valor_seguro(m_ie.group(1)) if m_ie else 0.0
        v_alq = limpiar_valor_seguro(m_alq.group(1)) if m_alq else 0.0
        v_otr = limpiar_valor_seguro(m_otr.group(1)) if m_otr else 0.0
        
        total_real = v_tot - v_iva - v_ie - v_alq - v_otr
        excedente = 0.0

    else:
        # Lógica genérica simplificada (puedes mantener tus otros elif aquí arriba)
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        potencia, fecha, dias, total_real, excedente = 0.0, "No encontrada", 0, 0.0, 0.0

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos.get('punta', 0.0), "Consumo Llano (kWh)": consumos.get('llano', 0.0),
        "Consumo Valle (kWh)": consumos.get('valle', 0.0), "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- Código Streamlit (Sigue igual que el tuyo) ---
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
                    "Mes/Fecha": fact['Fecha'],
                    "Compañía/Tarifa": f"📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'],
                    "Ahorro": 0.0,
                    "Dias_Factura": fact['Días']
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
                            "Dias_Factura": fact['Días']
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            
            df_solo_ofertas = df_comp[~df_comp["Compañía/Tarifa"].str.contains("📍 TU FACTURA")]
            ranking_total = df_solo_ofertas.groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index()
            ranking_total = ranking_total.sort_values(by="Ahorro", ascending=False)

            st.divider()
            
            if not ranking_total.empty:
                mejor_opcion_nombre = ranking_total.iloc[0]['Compañía/Tarifa']
                st.subheader("🏆 Resultado del Análisis")
                c1, c2 = st.columns(2)
                with c1: st.success(f"La mejor compañía es: **{mejor_opcion_nombre}**")
                with c2: st.metric(label="Ahorro Total Acumulado", value=f"{round(ranking_total.iloc[0]['Ahorro'], 2)} €")

            st.subheader("📊 Comparativa Detallada por Factura")
            df_mostrar = df_comp.drop(columns=['Dias_Factura'], errors='ignore')
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Detalle Comparativa')
                ranking_total.to_excel(writer, index=False, sheet_name='Ranking Ahorro')
                df_resumen_pdfs.to_excel(writer, index=False, sheet_name='Datos Facturas Originales')

            st.download_button(
                label="📥 Descargar Informe Completo",
                data=buffer_excel.getvalue(),
                file_name="estudio_ahorro_energetico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
