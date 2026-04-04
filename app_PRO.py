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

    compania = "Genérica / Desconocida" # Valor por defecto

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
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
        v_pot = float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0
        v_ene = float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0
        total_real = v_pot + v_ene
        m_exc = re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = float(m_exc.group(1).replace(',', '.')) if m_exc else 0.0

    elif es_total_energies:
        compania = "TotalEnergies"
        m_fecha = re.search(r'Fecha\s+emisión:\s*([\d.]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias_meta = re.search(r'(\d+)\s+día\(s\)', texto_completo, re.IGNORECASE)
        dias = int(m_dias_meta.group(1)) if m_dias_meta else 0
        m_pot_meta = re.search(r'Potencia\s+P1:\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        potencia = float(m_pot_meta.group(1).replace(',', '.')) if m_pot_meta else 0.0
        total_real = 0.0
        lineas = texto_completo.split('\n')
        for linea in lineas:
            linea_limpia = linea.strip()
            if re.search(r'^(\d{2}\.\d{2}\.\d{4})|(\d+\s+día\(s\))', linea_limpia):
                m_valor = re.findall(r'([\d,.]+)\s*€\s*$', linea_limpia)
                if m_valor:
                    total_real += float(m_valor[-1].replace('.', '').replace(',', '.'))

        def extraer_kwh(tipo, texto):
            patron = rf'{tipo}.*?([\d,.]+)\s*kWh'
            matches = re.findall(patron, texto, re.IGNORECASE)
            if matches: return float(matches[-1].replace('.', '').replace(',', '.'))
            return 0.0

        consumos = {
            'punta': extraer_kwh('Punta', texto_completo),
            'llano': extraer_kwh('Llano', texto_completo),
            'valle': extraer_kwh('Valle', texto_completo)
        }
        if sum(consumos.values()) == 0:
            m_gen = re.search(r'(\d+)\s*kWh\s+[\d,.]+\s*€/kWh', texto_completo)
            if m_gen: consumos['punta'] = float(m_gen.group(1))
        excedente = 0.0

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
        
        m_exc = re.search(r'Valoración\s+excedentes\s*(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(m_exc.group(1).replace(',', '.'))) if m_exc else 0.0
        
        # --- Modificación solicitada para Naturgy ---
        m_subtotal = re.search(r'Subtotal\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        if m_subtotal:
            total_real = float(m_subtotal.group(1).replace(',', '.'))
        else:
            m_total_elec = re.search(r'Total\s+electricidad\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = float(m_total_elec.group(1).replace(',', '.')) if m_total_elec else 0.0

   elif es_endesa_luz:
        compania = "Endesa Energía"
        # Fecha de emisión
        m_fecha_etiqueta = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha_etiqueta.group(1) if m_fecha_etiqueta else "No encontrada"
        
        # Días de facturación
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        # Potencia contratada
        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        
        def limpiar_valor_endesa(patron, texto):
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                # Quitamos puntos de miles y cambiamos coma por punto decimal
                valor_sucio = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
                try: return float(valor_sucio)
                except: return 0.0
            return 0.0

        val_potencia = limpiar_valor_endesa(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo)
        val_energia = limpiar_valor_endesa(r'Energ[ií]a(?:\s+consumida(?:\s+de\s+la\s+red)?)?[\s.]*([\d\s.,]+)€', texto_completo)
        total_real = val_potencia + val_energia

        # --- CORRECCIÓN DE CONSUMOS ---
        # Buscamos la palabra y capturamos el último número de la línea (soporta negativos en columnas previas)
        m_punta = re.search(r'^Punta.*\s+([\d,.]+)$', texto_completo, re.MULTILINE | re.IGNORECASE)
        m_llano = re.search(r'^Llano.*\s+([\d,.]+)$', texto_completo, re.MULTILINE | re.IGNORECASE)
        m_valle = re.search(r'^Valle.*\s+([\d,.]+)$', texto_completo, re.MULTILINE | re.IGNORECASE)
        
        # Si no encuentra por línea completa, intentamos una versión más flexible
        if not m_punta:
            m_punta = re.search(r'Punta(?:\s+[\d,.-]+){4}\s+([\d,.]+)', texto_completo)
        if not m_llano:
            m_llano = re.search(r'Llano(?:\s+[\d,.-]+){4}\s+([\d,.]+)', texto_completo)
        if not m_valle:
            m_valle = re.search(r'Valle(?:\s+[\d,.-]+){4}\s+([\d,.]+)', texto_completo)

        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }

        # Captura de excedentes (importante para facturas con Solar)
        m_exc = re.search(r'Energia\s+vertida\s+a\s+la\s+red\s+([\d,.]+)\s+kWh', texto_completo, re.IGNORECASE)
        excedente = float(m_exc.group(1).replace(',', '.')) if m_exc else 0.0


    elif es_repsol:
        compania = "Repsol"
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
        consumos = {'punta': float(m_consumo_gen.group(1).replace(',', '.')) if m_consumo_gen else 0.0, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        compania = "Iberdrola"
        patron_potencia = r'Potencia\s+punta:\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_dias = r'Potencia\s+facturada.*?(\d+)\s+días'
        match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_periodo = r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})'
        match_periodo = re.search(patron_periodo, texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = match_periodo.group(2) if match_periodo else "No encontrada"
        m_punta = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_llano = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_valle = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_imp_potencia = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_imp_energia = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_imp_potencia.group(1).replace(',', '.')) if m_imp_potencia else 0.0) + (float(m_imp_energia.group(1).replace(',', '.')) if m_imp_energia else 0.0)
        excedente = 0.0

    else:
        if es_xxi: compania = "Energía XXI"
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
        match_dias = re.search(r'(\d+)\s*días', texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        match_excedente = re.search(r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
        
        m_val_pot_xxi = re.search(r'Por\s+potencia\s+contratada\s+.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_val_ene_xxi = re.search(r'Por\s+energía\s+consumida\s+.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        if m_val_pot_xxi and m_val_ene_xxi:
            total_real = float(m_val_pot_xxi.group(1).replace(',', '.')) + float(m_val_ene_xxi.group(1).replace(',', '.'))
        else:
            match_total = re.search(r'Total\s+electricidad\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

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

            # --- PARTE AÑADIDA: VISUALIZACIÓN IGUAL A LA FOTO ---
            st.subheader("📊 Comparativa Detallada por Factura")
            
            df_mostrar = df_comp.drop(columns=['Dias_Factura'], errors='ignore')
            
            st.dataframe(
                df_mostrar,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Coste (€)": st.column_config.NumberColumn(format="%.2f"),
                    "Ahorro": st.column_config.NumberColumn(
                        format="%.2f",
                        help="Ahorro respecto a tu factura actual"
                    ),
                }
            )

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
