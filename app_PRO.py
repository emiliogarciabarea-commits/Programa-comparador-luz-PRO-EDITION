import pdfplumber
import re
import pandas as pd
import gradio as gr
import io
import os

def extraer_datos_factura(pdf_input):
    texto_completo = ""
    # Gradio puede pasar una ruta (string) o un objeto de archivo
    path = pdf_input if isinstance(pdf_input, str) else pdf_input.name
    
    with pdfplumber.open(path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)

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

    elif es_endesa_luz:
        m_fecha_etiqueta = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha_etiqueta.group(1) if m_fecha_etiqueta else (re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo) else "No encontrada")
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        def limpiar_valor_endesa(patron, texto):
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                valor_limpio = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
                try: return float(valor_limpio)
                except: return 0.0
            return 0.0

        val_potencia = limpiar_valor_endesa(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo)
        val_energia = limpiar_valor_endesa(r'Energía\s+\.+\s*([\d\s.,]+)€', texto_completo)
        total_real = val_potencia + val_energia
        m_punta = re.search(r'Punta\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Llano\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Valle\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
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
        match_potencia = re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        match_dias = re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(match_dias.group(1)) if match_dias else 0
        match_periodo = re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL)
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
        if es_naturgy:
            match_dias_nat = re.search(r'Término\s+potencia\s+P1.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
            dias = int(match_dias_nat.group(1)) if match_dias_nat else 0
        else:
            match_dias = re.search(r'(\d+)\s*días', texto_completo)
            dias = int(match_dias.group(1)) if match_dias else 0
        match_excedente = re.search(r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE)
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
        "Total Real": round(total_real, 2)
    }

def procesar_todo(archivos_pdf):
    excel_path = "tarifas_companias.xlsx"
    if not archivos_pdf:
        return "Error: No has subido archivos.", None, None, None, None
    
    if not os.path.exists(excel_path):
        return f"Error: No se encuentra {excel_path}", None, None, None, None

    datos_facturas = []
    for f in archivos_pdf:
        try:
            res = extraer_datos_factura(f)
            res['Archivo'] = os.path.basename(f.name)
            datos_facturas.append(res)
        except Exception as e:
            print(f"Error en {f.name}: {e}")

    if not datos_facturas:
        return "No se extrajeron datos.", None, None, None, None

    df_resumen_pdfs = pd.DataFrame(datos_facturas)
    df_tarifas = pd.read_excel(excel_path)
    resultados_finales = []

    for _, fact in df_resumen_pdfs.iterrows():
        resultados_finales.append({
            "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",
            "Coste (€)": fact['Total Real'], "Ahorro": 0.0
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
    df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
    
    df_solo_ofertas = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"]
    ranking_total = df_solo_ofertas.groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index().sort_values(by="Ahorro", ascending=False)

    mejor_cia = ranking_total.iloc[0]['Compañía/Tarifa'] if not ranking_total.empty else "N/A"
    mejor_ahorro = f"{round(ranking_total.iloc[0]['Ahorro'], 2)} €" if not ranking_total.empty else "0 €"

    # Crear Excel para descarga
    output_path = "estudio_ahorro_energetico.xlsx"
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_comp.to_excel(writer, index=False, sheet_name='Detalle')
        ranking_total.to_excel(writer, index=False, sheet_name='Ranking')
        df_resumen_pdfs.to_excel(writer, index=False, sheet_name='Datos_Originales')

    return f"Mejor opción: {mejor_cia}", mejor_ahorro, df_resumen_pdfs, df_comp, output_path

# --- INTERFAZ GRADIO ---
with gr.Blocks(title="Comparador Energético PRO") as demo:
    gr.Markdown("# ⚡ Comparador de Facturas Eléctricas Pro")
    
    with gr.Row():
        pdf_files = gr.File(label="Sube tus facturas PDF", file_count="multiple", file_types=[".pdf"])
    
    btn = gr.Button("🔍 Iniciar Análisis", variant="primary")
    
    with gr.Row():
        res_cia = gr.Textbox(label="🏆 Ganadora")
        res_ahorro = gr.Textbox(label="💰 Ahorro Total")
    
    with gr.Tabs():
        with gr.TabItem("📋 Datos Extraídos"):
            out_resumen = gr.Dataframe()
        with gr.TabItem("📊 Comparativa Completa"):
            out_comp = gr.Dataframe()
        with gr.TabItem("📥 Descargar"):
            out_file = gr.File(label="Descargar Informe Excel")

    btn.click(
        fn=procesar_todo,
        inputs=pdf_files,
        outputs=[res_cia, res_ahorro, out_resumen, out_comp, out_file]
    )

if __name__ == "__main__":
    demo.launch()
