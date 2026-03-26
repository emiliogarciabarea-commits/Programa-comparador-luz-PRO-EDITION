elif re.search(r'Endesa', texto_completo, re.IGNORECASE):
        # 1. Fecha de emisión (Formato DD/MM/AAAA en la misma fila que "Fecha emisión factura")
        m_fecha = re.search(r'Fecha emisión factura:\s*([\d/]+)', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"

        # 2. Días (En el apartado "INFORMACIÓN DEL CONSUMO ELÉCTRICO" con formato "(DD días)")
        m_dias = re.search(r'INFORMACIÓN\s+DEL\s+CONSUMO\s+ELÉCTRICO.*?\((\d+)\s+días\)', texto_completo, re.DOTALL | re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        # 3. Potencia (Número junto a kW)
        # Se busca habitualmente en el detalle o datos de contrato
        m_pot = re.search(r'([\d,.]+)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        # 4, 5 y 6. Energía en Punta, Llano y Valle (Número seguido de kWh en sus respectivas filas)
        # Se busca en la tabla de "INFORMACIÓN DEL CONSUMO ELÉCTRICO A efectos de facturación"
        m_punta = re.search(r'Punta.*?kWh\s*([\d,.]+)', texto_completo, re.DOTALL | re.IGNORECASE)
        m_llano = re.search(r'Llano.*?([\d,.]+)\s*$', texto_completo, re.MULTILINE) # Suele ser el valor al final de la linea tras Llano
        # Ajuste de patrones para capturar específicamente los valores de la tabla de consumo:
        patron_energia_endesa = r'Punta.*?([\d,.]+)\s*\n\s*Llano.*?([\d,.]+)\s*\n\s*Valle.*?([\d,.]+)'
        match_energias = re.search(patron_energia_endesa, texto_completo, re.DOTALL | re.IGNORECASE)
        
        if match_energias:
            consumos = {
                'punta': float(match_energias.group(1).replace(',', '.')),
                'llano': float(match_energias.group(2).replace(',', '.')),
                'valle': float(match_energias.group(3).replace(',', '.'))
            }
        else:
            # Búsqueda individual si falla el bloque
            p = re.search(r'Punta\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+([\d,.]+)', texto_completo)
            l = re.search(r'Llano\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+([\d,.]+)', texto_completo)
            v = re.search(r'Valle\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+([\d,.]+)', texto_completo)
            consumos = {
                'punta': float(p.group(1).replace(',', '.')) if p else 0.0,
                'llano': float(l.group(1).replace(',', '.')) if l else 0.0,
                'valle': float(v.group(1).replace(',', '.')) if v else 0.0
            }

        # 7. Total Real (Suma de "Potencia" en € más la "Energia" en €)
        m_imp_pot = re.search(r'Potencia\s*([\d,.]+)\s*€', texto_completo)
        m_imp_ene = re.search(r'Energia\s*([\d,.]+)\s*€', texto_completo)
        
        val_pot = float(m_imp_pot.group(1).replace(',', '.')) if m_imp_pot else 0.0
        val_ene = float(m_imp_ene.group(1).replace(',', '.')) if m_imp_ene else 0.0
        total_real = val_pot + val_ene
        excedente = 0.0
