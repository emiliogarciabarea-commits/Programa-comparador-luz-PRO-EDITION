if es_endesa_luz:
        # 1. Fecha de emisión (Buscamos la fecha DD/MM/AAAA tras el texto clave)
        m_fecha = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"

        # 2. Días (Buscamos el número dentro de paréntesis seguido de la palabra días)
        m_dias = re.search(r'\((\d+)\s+días\)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        # 3. Potencia en kW (Buscamos un número con coma seguido de kW)
        # Usamos un patrón que evite capturar fechas o importes en €
        m_pot = re.search(r'(\d+,\d+)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        # 4. Energías (Punta, Llano, Valle)
        # Buscamos la palabra y el primer valor en kWh que aparezca después
        m_punta = re.search(r'Punta.*?([\d,.]+)\s*kWh', texto_completo, re.DOTALL | re.IGNORECASE)
        m_llano = re.search(r'Llano.*?([\d,.]+)\s*kWh', texto_completo, re.DOTALL | re.IGNORECASE)
        m_valle = re.search(r'Valle.*?([\d,.]+)\s*kWh', texto_completo, re.DOTALL | re.IGNORECASE)
        
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }

        # 5. Total Real (Suma de los importes de Potencia y Energía en el resumen)
        # Capturamos el importe que va justo antes o después de la palabra en el resumen inicial
        m_imp_pot = re.search(r'Potencia\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_imp_ene = re.search(r'Energia\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        
        val_pot = float(m_imp_pot.group(1).replace(',', '.')) if m_imp_pot else 0.0
        val_ene = float(m_imp_ene.group(1).replace(',', '.')) if m_imp_ene else 0.0
        total_real = val_pot + val_ene
        excedente = 0.0
