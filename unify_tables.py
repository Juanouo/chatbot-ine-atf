#!/usr/bin/env python3
"""
Unify ene_prueba_inicial.parquet and ene_sexo_prueba_inicial.parquet into a single table.

Target structure:
    indicador | valor_indicador | grupo | valor_grupo | año | mes
"""

import pandas as pd
import os
import numpy as np
from pathlib import Path


mapa_regiones = {
    "Arica y Parinacota": "15",
    "Tarapacá": "1",
    "Antofagasta": "2",
    "Atacama": "3",
    "Coquimbo": "4",
    "Valparaíso": "5",

    "Metropolitana": "13",
    "O'Higgins": "6",
    "Maule": "7",
    "Ñuble": "16",

    "Biobío": "8",

    "Araucanía": "9",
    "Los Ríos": "14",
    "Los Lagos": "10",

    "Aysén": "11",
    "Magallanes": "12"
}
mapa_regiones = {v:k for k,v in mapa_regiones.items()}  # Reverse mapping for regions
# Get the directory where this script is located

data_dir = Path('data/')
intermediate_dir = data_dir / 'intermediate'

df_enusc = pd.read_parquet(intermediate_dir / 'enusc_unificado.parquet').drop(columns=['codigo_indicador'])
df_enusc['mes'] = np.nan
df_ene = pd.read_parquet(intermediate_dir / 'ene_unificado.parquet')
df_ene['indicador'] = df_ene['indicador'].replace({'fuerza_trabajo': 'personas_fuerza_trabajo',
                                                   'poblacion_edad_trabajar': 'personas_edad_trabajar'})

indicadores = df_ene.indicador.value_counts().index
indicadores_personas = indicadores[indicadores.str.contains('persona')]
# Pasamos cifras a su valor completo
df_ene.loc[df_ene.indicador.isin(indicadores_personas), 'valor_indicador'] = df_ene.loc[df_ene.indicador.isin(indicadores_personas), 'valor_indicador'] * 1000

df_ipc = pd.read_parquet(intermediate_dir / 'ipc_general.parquet')
df_ipc.indicador = df_ipc.indicador.replace({'variacion_mensual': 'ipc_variacion_mensual',
                                             'variacion_12_meses': 'ipc_variacion_12_meses'})

df_total = pd.concat([df_ene, df_enusc, df_ipc], ignore_index=True)
#df_total.grupo = df_total.grupo.replace('nacional', np.nan)
df_total.valor_grupo = df_total.valor_grupo.replace('Total País', np.nan)
df_total.valor_grupo = df_total.valor_grupo.replace('-', np.nan)

# Redondeamos cifras
v = df_total.valor_indicador
df_total.valor_indicador = np.where(
    v < 1,
    np.round(v, 4),
    np.where(
        v <= 1000,
        np.round(v, 2),
        np.round(v, 0)
    )
)

df_total.mes = df_total.mes.astype('Int32', errors='ignore')
df_total.año = df_total.año.astype('Int32', errors='ignore')
df_total.valor_indicador

# Mapeamos valores de las regiones
filter_regs = df_total.grupo == 'region'
df_total.loc[filter_regs, 'valor_grupo' ] = df_total.loc[filter_regs, ].valor_grupo.map(mapa_regiones)



output_path = data_dir / 'current/total_unificado.parquet'

df_total = df_total[df_total.grupo.ne('nse')] # Quitamos nse
df_total
df_total.to_parquet(output_path, index=False)

df_total[df_total.grupo.eq('region')].indicador.value_counts()
print(f"✅ Unified table saved to: {output_path}")
print(f"\nShape: {df_total.shape}")
print(f"\nColumns: {df_total.columns.tolist()}")
print(f"\nFirst 10 rows:")
print(df_total.head(10))
print(f"\nLast 10 rows:")
print(df_total.tail(10))
print(f"\nUnique values:")
print(f"  - indicador: {df_total['indicador'].unique()}")
print(f"  - grupo: {df_total['grupo'].unique()}")
print(f"  - valor_grupo: {df_total['valor_grupo'].unique()}")
# # Combine both dataframes
# df_ene = pd.concat([df_nacional_unified, df_sexo_unified], ignore_index=True)

# # Sort by indicador, año, mes, grupo
# df_ene = df_ene.sort_values(['indicador', 'año', 'mes', 'grupo', 'valor_grupo']).reset_index(drop=True)

# # Save to parquet

# df_ene.grupo = df_ene.grupo.replace('-', np.nan)
# df_ene.mes = df_ene.mes.replace('-', np.nan)


# df_ene['frecuencia'] = np.where(df_ene.mes.isna(), 'anual', 'mensual')

# df_ene.to_parquet(data_dir_old / 'ene_unificado.parquet', index=False)


# enusc = pd.read_parquet(data_dir_old / 'enusc_unificado.parquet')\
#     .drop(columns=['codigo_indicador'])
# enusc = enusc[~enusc.grupo.isin(['nse', 'quintil'])]

# data_dir_old = data_dir / 'old'
# # Read both parquet files
# df_nacional = pd.read_parquet(data_dir_old / 'ene_prueba_inicial.parquet')
# df_sexo = pd.read_parquet(data_dir_old / 'ene_sexo_prueba_inicial.parquet')
# # Process national data (ene_prueba_inicial)
# # grupo = "-", valor_grupo = "-", mes from original data
# df_nacional_unified = pd.DataFrame({
#     'indicador': df_nacional['indicador'],
#     'valor_indicador': df_nacional['valor'],
#     'grupo': '-',
#     'valor_grupo': '-',
#     'año': df_nacional['anio'].astype(int),
#     'mes': df_nacional['mes'].astype(int).astype(str)  # Keep month as string for consistency
# })

# # Process sexo data (ene_sexo_prueba_inicial)
# # grupo = "sexo", valor_grupo = hombre/mujer, mes = "-" (yearly data)
# df_sexo_unified = pd.DataFrame({
#     'indicador': df_sexo['indicador'],
#     'valor_indicador': df_sexo['valor'],
#     'grupo': 'sexo',
#     'valor_grupo': df_sexo['sexo'],
#     'año': df_sexo['anio'].astype(int),
#     'mes': '-'  # Yearly data has no month
# })
# df_enusc.codigo_indicador