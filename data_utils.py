# data_utils.py
import pandas as pd
import geopandas as gpd

def load_crime_data(uploaded_file):
    """
    Lê o CSV com separador ';' e realiza a limpeza dos dados,
    selecionando as colunas relevantes e convertendo as coordenadas.
    """
    df = pd.read_csv(uploaded_file, sep=";", on_bad_lines='skip')
    df.columns = df.columns.str.strip()
    colunas_interesse = [
        'DATA_FATO', 'HORARIO_FATO', 'LATITUDE', 'LONGITUDE',
        'DESCR_NATUREZA_PRINCIPAL', 'MUNICIPIO', 'UF',
        'FAIXA_HORA_1', 'FAIXA_HORA_6'
    ]
    colunas_existentes = [c for c in colunas_interesse if c in df.columns]
    df = df[colunas_existentes].copy()
    
    # Converter LATITUDE e LONGITUDE (substituindo vírgula por ponto)
    df['LATITUDE'] = df['LATITUDE'].astype(str).str.replace(",", ".").astype(float)
    df['LONGITUDE'] = df['LONGITUDE'].astype(str).str.replace(",", ".").astype(float)
    
    # Filtrar coordenadas válidas
    valid_coords = (df['LATITUDE'].between(-90, 90)) & (df['LONGITUDE'].between(-180, 180))
    df = df[valid_coords]
    df.dropna(subset=['LATITUDE', 'LONGITUDE'], inplace=True)
    df = df[(df['LATITUDE'] != 0) & (df['LONGITUDE'] != 0)]
    
    # Criar coluna DATETIME_FATO a partir de DATA_FATO e HORARIO_FATO
    if 'DATA_FATO' in df.columns and 'HORARIO_FATO' in df.columns:
        df['DATA_FATO'] = pd.to_datetime(df['DATA_FATO'], errors='coerce')
        df['HORARIO_FATO'] = df['HORARIO_FATO'].fillna('00:00:00')
        df['DATETIME_FATO'] = df.apply(
            lambda row: pd.to_datetime(
                f"{row['DATA_FATO'].strftime('%Y-%m-%d')} {row['HORARIO_FATO']}",
                errors='coerce'
            ) if pd.notnull(row['DATA_FATO']) else pd.NaT,
            axis=1
        )
    
    df.drop_duplicates(inplace=True)
    return df

def create_geodataframe(df):
    """
    Converte o DataFrame em um GeoDataFrame com CRS EPSG:4326.
    """
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df['LONGITUDE'], df['LATITUDE']),
        crs="EPSG:4326"
    )
    return gdf
