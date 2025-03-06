import streamlit as st
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import date
import osmnx as ox

from data_utils import load_crime_data, create_geodataframe
from network_utils import get_osmnx_graph, snap_points_to_network, compute_node_densities
from algorithms import phar, i_phar, shar, expansive_network
from cluster_table import build_cluster_table_polygons, build_cluster_table_subgraphs, show_cluster_table_as_links


st.set_page_config('HotSpots',layout='wide')
# Direitos autorais (citação da tese)
st.sidebar.markdown("""
**Baseado na tese:**

NUNES JUNIOR, Francisco Carlos Freire. *Geração de mapas de hotspots em redes de ruas para predição de crimes.* 2020. 108 f. Dissertação (Mestrado em Ciência da Computação) - Universidade Federal do Ceará, Fortaleza, 2020.  
Disponível em: [http://repositorio.ufc.br/handle/riufc/51515](http://repositorio.ufc.br/handle/riufc/51515)
""")

def main():
    st.title("Patrulhamento Orientado por HotSposts - POH")
    
    st.sidebar.header("Configurações")
    eps_kde = st.sidebar.slider("Bandwidth (KDE restrito à rede)", 50, 1000, 200, 
                                help="Valor ideal depende da densidade urbana. Ex.: 200 para áreas densas.")
    dens_threshold = st.sidebar.slider("Limiar de densidade", 0.1, 50.0, 1.0, 
                                       help="Valores menores identificam mais hotspots; ajuste conforme os dados.")
    dist_threshold = st.sidebar.slider("Distância de cluster (para PHAR/SHAR)", 100, 1000, 300, 
                                       help="Valor ideal depende da escala da cidade. Ex.: 300 metros.")
    
    alg_option = st.sidebar.selectbox(
        "Algoritmo de Geração de Hotspots",
        ["PHAR", "i-PHAR", "SHAR", "Expansive Network"]
    )
    
    uploaded_file = st.file_uploader("Carregue o arquivo CSV com os dados de crime", type=["csv"])
    
    if uploaded_file is not None:
        df_original = load_crime_data(uploaded_file)
        st.write("Exemplo de dados:", df_original.head())
        
        df = df_original.copy()
        
        # Filtro por MUNICÍPIO (opcional)
        if "MUNICIPIO" in df.columns:
            muni_list = sorted(df["MUNICIPIO"].dropna().unique())
            selected_municipio = st.sidebar.selectbox("Selecione um MUNICÍPIO (opcional)", [""] + muni_list)
        else:
            selected_municipio = ""
        if selected_municipio:
            df = df[df["MUNICIPIO"] == selected_municipio]
            uf_valor = df["UF"].iloc[0] if not df["UF"].empty else ""
            region_query = f"{selected_municipio}, {uf_valor}, Brazil"
        else:
            region_query = None
        
        # Filtro por natureza principal (opcional)
        if "DESCR_NATUREZA_PRINCIPAL" in df.columns:
            naturezas = sorted(df["DESCR_NATUREZA_PRINCIPAL"].dropna().unique())
            selected_naturezas = st.sidebar.multiselect("Naturezas (opcional)", naturezas)
            if selected_naturezas:
                df = df[df["DESCR_NATUREZA_PRINCIPAL"].isin(selected_naturezas)]
        
        # Filtros para FAIXA_HORA_1 e FAIXA_HORA_6 (opcionais)
        if "FAIXA_HORA_1" in df.columns:
            faixas1 = sorted(df["FAIXA_HORA_1"].dropna().unique())
            selected_faixa1 = st.sidebar.multiselect("FAIXA_HORA_1 (opcional)", faixas1)
            if selected_faixa1:
                df = df[df["FAIXA_HORA_1"].isin(selected_faixa1)]
        if "FAIXA_HORA_6" in df.columns:
            faixas6 = sorted(df["FAIXA_HORA_6"].dropna().unique())
            selected_faixa6 = st.sidebar.multiselect("FAIXA_HORA_6 (opcional)", faixas6)
            if selected_faixa6:
                df = df[df["FAIXA_HORA_6"].isin(selected_faixa6)]
        
        # Filtro temporal
        if "DATETIME_FATO" in df.columns and df["DATETIME_FATO"].notnull().any():
            min_date = df["DATETIME_FATO"].min().date()
            max_date = df["DATETIME_FATO"].max().date()
            date_range = st.sidebar.date_input("Intervalo de datas (opcional)", [min_date, max_date])
            if len(date_range) == 2:
                start_date, end_date = date_range
                df = df[(df["DATETIME_FATO"].dt.date >= start_date) & (df["DATETIME_FATO"].dt.date <= end_date)]
        
        if df.empty:
            st.warning("Nenhum dado encontrado com os filtros aplicados. Usando dados originais.")
            df = df_original.copy()
        
        gdf_crime = create_geodataframe(df)
        
        if region_query:
            try:
                G = get_osmnx_graph(region_query)
                st.write("Rede viária obtida. Número de nós:", len(G.nodes()))
            except Exception as e:
                st.error(f"Erro ao obter a rede viária para '{region_query}': {e}")
                st.warning("Verifique se o município está correto. Não foi possível gerar hotspots baseados na rede.")
                G = None
        else:
            st.warning("Nenhum MUNICÍPIO selecionado; não foi possível obter a rede viária. Hotspots baseados na rede não serão gerados.")
            G = None
        
        if G is not None:
            st.write("Calculando densidades (KDE restrito à rede, simplificado)...")
            densities = compute_node_densities(gdf_crime, G, bandwidth=eps_kde)
            
            st.write(f"Executando algoritmo: {alg_option} ...")
            if alg_option == "PHAR":
                polygons = phar(densities, G, density_threshold=dens_threshold, dist_threshold=dist_threshold)
                if not polygons:
                    st.warning("Nenhum hotspot foi gerado com o algoritmo PHAR. Verifique os parâmetros.")
                else:
                    poly_list = []
                    for cid, hull in polygons:
                        hull_4326 = gpd.GeoDataFrame(index=[0], geometry=[hull], crs="EPSG:3857").to_crs(epsg=4326).geometry.iloc[0]
                        poly_list.append((cid, hull_4326))
                    m_poly = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
                                                  gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
                    for cid, poly_obj in poly_list:
                        folium.GeoJson(
                            poly_obj,
                            style_function=lambda x, color="red": {
                                "fillColor": color,
                                "color": color,
                                "weight": 2,
                                "fillOpacity": 0.3
                            },
                            tooltip=f"Cluster {cid}"
                        ).add_to(m_poly)
                    st.subheader("Mapa PHAR (Polígonos)")
                    st_folium(m_poly, width=700, height=500)
                    
                    from cluster_table import build_cluster_table_polygons, show_cluster_table_as_links
                    df_table = build_cluster_table_polygons(poly_list)
                    st.subheader("Tabela de Clusters (PHAR)")
                    show_cluster_table_as_links(df_table)
                    
            elif alg_option == "i-PHAR":
                new_crimes = gdf_crime.geometry
                polygons = i_phar(densities, G, old_polygons=[], new_crimes=new_crimes,
                                  bandwidth=eps_kde, density_threshold=dens_threshold, dist_threshold=dist_threshold)
                if not polygons:
                    st.warning("Nenhum hotspot foi gerado com o algoritmo i-PHAR. Verifique os parâmetros.")
                else:
                    poly_list = []
                    for cid, hull in polygons:
                        hull_4326 = gpd.GeoDataFrame(index=[0], geometry=[hull], crs="EPSG:3857").to_crs(epsg=4326).geometry.iloc[0]
                        poly_list.append((cid, hull_4326))
                    m_poly = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
                                                  gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
                    for cid, poly_obj in poly_list:
                        folium.GeoJson(
                            poly_obj,
                            style_function=lambda x, color="green": {
                                "fillColor": color,
                                "color": color,
                                "weight": 2,
                                "fillOpacity": 0.3
                            },
                            tooltip=f"Cluster {cid}"
                        ).add_to(m_poly)
                    st.subheader("Mapa i-PHAR (Incremental Polígonos)")
                    st_folium(m_poly, width=700, height=500)
                    
                    from cluster_table import build_cluster_table_polygons, show_cluster_table_as_links
                    df_table = build_cluster_table_polygons(poly_list)
                    st.subheader("Tabela de Clusters (i-PHAR)")
                    show_cluster_table_as_links(df_table)
                    
            elif alg_option == "SHAR":
                from algorithms import shar
                subgraphs = shar(densities, G, density_threshold=dens_threshold, dist_threshold=dist_threshold)
                if not subgraphs:
                    st.warning("Nenhum hotspot foi gerado com o algoritmo SHAR. Verifique os parâmetros.")
                else:
                    m_shar = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
                                                  gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
                    edges_4326 = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index().to_crs(epsg=4326)
                    color_list = ["red", "green", "blue", "purple", "orange", "yellow"]
                    from shapely.geometry import LineString
                    for cid, edge_pairs in subgraphs:
                        color = color_list[cid % len(color_list)]
                        for (u, v) in edge_pairs:
                            mask_uv = ((edges_4326['u'] == u) & (edges_4326['v'] == v)) | ((edges_4326['u'] == v) & (edges_4326['v'] == u))
                            row_ = edges_4326[mask_uv]
                            if not row_.empty:
                                line = row_.iloc[0].geometry
                                if isinstance(line, LineString):
                                    coords = [(pt[1], pt[0]) for pt in line.coords]
                                    folium.PolyLine(coords, color=color, weight=3, tooltip=f"Cluster {cid}").add_to(m_shar)
                    st.subheader("Mapa SHAR (Subgraphs)")
                    st_folium(m_shar, width=700, height=500)
                    
                    from cluster_table import build_cluster_table_subgraphs, show_cluster_table_as_links
                    df_table = build_cluster_table_subgraphs(subgraphs, G)
                    st.subheader("Tabela de Clusters (SHAR)")
                    show_cluster_table_as_links(df_table)
                    
            elif alg_option == "Expansive Network":
                from algorithms import expansive_network
                expansions = expansive_network(densities, G, density_threshold=dens_threshold)
                if not expansions:
                    st.warning("Nenhum hotspot foi gerado com o algoritmo Expansive Network. Verifique os parâmetros.")
                else:
                    m_exp = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
                                                 gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
                    edges_4326 = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index().to_crs(epsg=4326)
                    color_list = ["red", "green", "blue", "purple", "orange", "yellow"]
                    from shapely.geometry import LineString
                    for c_id, node_set, edge_pairs in expansions:
                        color = color_list[c_id % len(color_list)]
                        for (u, v) in edge_pairs:
                            mask_uv = ((edges_4326['u'] == u) & (edges_4326['v'] == v)) | ((edges_4326['u'] == v) & (edges_4326['v'] == u))
                            row_ = edges_4326[mask_uv]
                            if not row_.empty:
                                line = row_.iloc[0].geometry
                                if isinstance(line, LineString):
                                    coords = [(pt[1], pt[0]) for pt in line.coords]
                                    folium.PolyLine(coords, color=color, weight=3, tooltip=f"Cluster {c_id}").add_to(m_exp)
                    st.subheader("Mapa Expansive Network")
                    st_folium(m_exp, width=700, height=500)
                    
                    from cluster_table import build_cluster_table_subgraphs, show_cluster_table_as_links
                    df_table = build_cluster_table_subgraphs(expansions, G)
                    st.subheader("Tabela de Clusters (Expansive Network)")
                    show_cluster_table_as_links(df_table)
        else:
            st.warning("Nenhum MUNICÍPIO selecionado ou rede indisponível. Não foi possível gerar hotspots baseados na rede. Exibindo apenas os pontos.")
            center_lat = gdf_crime.to_crs(epsg=4326).geometry.y.mean()
            center_lon = gdf_crime.to_crs(epsg=4326).geometry.x.mean()
            m_ = folium.Map(location=[center_lat, center_lon], zoom_start=12)
            MarkerCluster().add_to(m_)
            for _, row in gdf_crime.to_crs(epsg=4326).iterrows():
                folium.Marker(location=[row.geometry.y, row.geometry.x]).add_to(m_)
            st_folium(m_, width=700, height=500)
        
        if st.button("Exportar hotspots como shapefile"):
            try:
                gdf_crime.to_file("hotspots_resultantes.shp")
                st.success("Arquivo exportado como 'hotspots_resultantes.shp'")
            except Exception as e:
                st.error(f"Erro na exportação: {e}")
    else:
        st.warning("Carregue um arquivo CSV para iniciar.")

if __name__ == "__main__":
    main()




# import streamlit as st
# import geopandas as gpd
# import folium
# from folium.plugins import MarkerCluster
# from streamlit_folium import st_folium
# from datetime import date
# import osmnx as ox

# from data_utils import load_crime_data, create_geodataframe
# from network_utils import get_osmnx_graph, snap_points_to_network, compute_node_densities
# from algorithms import phar, i_phar, shar, expansive_network
# from cluster_table import build_cluster_table_polygons, build_cluster_table_subgraphs, show_cluster_table_as_links

# def main():
#     st.title("Hotspots de Crimes - PHAR, i-PHAR, SHAR, Expansive Network")
    
#     st.sidebar.header("Configurações")
#     eps_kde = st.sidebar.slider("Bandwidth (KDE restrito à rede)", 50, 1000, 200, 
#                                 help="Valor ideal depende da densidade urbana. Ex.: 200 para áreas densas.")
#     dens_threshold = st.sidebar.slider("Limiar de densidade", 0.1, 50.0, 1.0, 
#                                        help="Valores menores identificam mais hotspots; ajuste conforme os dados.")
#     dist_threshold = st.sidebar.slider("Distância de cluster (para PHAR/SHAR)", 100, 1000, 300, 
#                                        help="Valor ideal depende da escala da cidade. Ex.: 300 metros.")
    
#     alg_option = st.sidebar.selectbox(
#         "Algoritmo de Geração de Hotspots",
#         ["PHAR", "i-PHAR", "SHAR", "Expansive Network"]
#     )
    
#     uploaded_file = st.file_uploader("Carregue o arquivo CSV com os dados de crime", type=["csv"])
    
#     if uploaded_file is not None:
#         df_original = load_crime_data(uploaded_file)
#         st.write("Exemplo de dados:", df_original.head())
        
#         df = df_original.copy()
        
#         # Filtro por MUNICÍPIO (opcional)
#         if "MUNICIPIO" in df.columns:
#             muni_list = sorted(df["MUNICIPIO"].dropna().unique())
#             selected_municipio = st.sidebar.selectbox("Selecione um MUNICÍPIO (opcional)", [""] + muni_list)
#         else:
#             selected_municipio = ""
#         if selected_municipio:
#             df = df[df["MUNICIPIO"] == selected_municipio]
#             uf_valor = df["UF"].iloc[0] if not df["UF"].empty else ""
#             region_query = f"{selected_municipio}, {uf_valor}, Brazil"
#         else:
#             region_query = None
        
#         # Filtro por natureza principal (opcional)
#         if "DESCR_NATUREZA_PRINCIPAL" in df.columns:
#             naturezas = sorted(df["DESCR_NATUREZA_PRINCIPAL"].dropna().unique())
#             selected_naturezas = st.sidebar.multiselect("Naturezas (opcional)", naturezas)
#             if selected_naturezas:
#                 df = df[df["DESCR_NATUREZA_PRINCIPAL"].isin(selected_naturezas)]
        
#         # Filtros para FAIXA_HORA_1 e FAIXA_HORA_6 (opcionais)
#         if "FAIXA_HORA_1" in df.columns:
#             faixas1 = sorted(df["FAIXA_HORA_1"].dropna().unique())
#             selected_faixa1 = st.sidebar.multiselect("FAIXA_HORA_1 (opcional)", faixas1)
#             if selected_faixa1:
#                 df = df[df["FAIXA_HORA_1"].isin(selected_faixa1)]
#         if "FAIXA_HORA_6" in df.columns:
#             faixas6 = sorted(df["FAIXA_HORA_6"].dropna().unique())
#             selected_faixa6 = st.sidebar.multiselect("FAIXA_HORA_6 (opcional)", faixas6)
#             if selected_faixa6:
#                 df = df[df["FAIXA_HORA_6"].isin(selected_faixa6)]
        
#         # Filtro temporal
#         if "DATETIME_FATO" in df.columns and df["DATETIME_FATO"].notnull().any():
#             min_date = df["DATETIME_FATO"].min().date()
#             max_date = df["DATETIME_FATO"].max().date()
#             date_range = st.sidebar.date_input("Intervalo de datas (opcional)", [min_date, max_date])
#             if len(date_range) == 2:
#                 start_date, end_date = date_range
#                 df = df[(df["DATETIME_FATO"].dt.date >= start_date) & (df["DATETIME_FATO"].dt.date <= end_date)]
        
#         if df.empty:
#             st.warning("Nenhum dado encontrado com os filtros aplicados. Usando dados originais.")
#             df = df_original.copy()
        
#         gdf_crime = create_geodataframe(df)
        
#         if region_query:
#             try:
#                 G = get_osmnx_graph(region_query)
#                 st.write("Rede viária obtida. Número de nós:", len(G.nodes()))
#             except Exception as e:
#                 st.error(f"Erro ao obter a rede viária para '{region_query}': {e}")
#                 st.warning("Verifique se o município está correto. Não foi possível gerar hotspots baseados na rede.")
#                 G = None
#         else:
#             st.warning("Nenhum MUNICÍPIO selecionado; não foi possível obter a rede viária. Hotspots baseados na rede não serão gerados.")
#             G = None
        
#         if G is not None:
#             st.write("Calculando densidades (KDE restrito à rede, simplificado)...")
#             densities = compute_node_densities(gdf_crime, G, bandwidth=eps_kde)
            
#             st.write(f"Executando algoritmo: {alg_option} ...")
#             if alg_option == "PHAR":
#                 polygons = phar(densities, G, density_threshold=dens_threshold, dist_threshold=dist_threshold)
#                 if not polygons:
#                     st.warning("Nenhum hotspot foi gerado com o algoritmo PHAR. Verifique os parâmetros.")
#                 else:
#                     poly_list = []
#                     for cid, hull in polygons:
#                         hull_4326 = gpd.GeoDataFrame(index=[0], geometry=[hull], crs="EPSG:3857").to_crs(epsg=4326).geometry.iloc[0]
#                         poly_list.append((cid, hull_4326))
#                     m_poly = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
#                                                   gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
#                     for cid, poly_obj in poly_list:
#                         folium.GeoJson(
#                             poly_obj,
#                             style_function=lambda x, color="red": {
#                                 "fillColor": color,
#                                 "color": color,
#                                 "weight": 2,
#                                 "fillOpacity": 0.3
#                             },
#                             tooltip=f"Cluster {cid}"
#                         ).add_to(m_poly)
#                     st.subheader("Mapa PHAR (Polígonos)")
#                     st_folium(m_poly, width=700, height=500)
                    
#                     df_table = build_cluster_table_polygons(poly_list)
#                     st.subheader("Tabela de Clusters (PHAR)")
#                     show_cluster_table_as_links(df_table)
                    
#             elif alg_option == "i-PHAR":
#                 new_crimes = gdf_crime.geometry
#                 polygons = i_phar(densities, G, old_polygons=[], new_crimes=new_crimes,
#                                   bandwidth=eps_kde, density_threshold=dens_threshold, dist_threshold=dist_threshold)
#                 if not polygons:
#                     st.warning("Nenhum hotspot foi gerado com o algoritmo i-PHAR. Verifique os parâmetros.")
#                 else:
#                     poly_list = []
#                     for cid, hull in polygons:
#                         hull_4326 = gpd.GeoDataFrame(index=[0], geometry=[hull], crs="EPSG:3857").to_crs(epsg=4326).geometry.iloc[0]
#                         poly_list.append((cid, hull_4326))
#                     m_poly = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
#                                                   gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
#                     for cid, poly_obj in poly_list:
#                         folium.GeoJson(
#                             poly_obj,
#                             style_function=lambda x, color="green": {
#                                 "fillColor": color,
#                                 "color": color,
#                                 "weight": 2,
#                                 "fillOpacity": 0.3
#                             },
#                             tooltip=f"Cluster {cid}"
#                         ).add_to(m_poly)
#                     st.subheader("Mapa i-PHAR (Incremental Polígonos)")
#                     st_folium(m_poly, width=700, height=500)
                    
#                     df_table = build_cluster_table_polygons(poly_list)
#                     st.subheader("Tabela de Clusters (i-PHAR)")
#                     show_cluster_table_as_links(df_table)
                    
#             elif alg_option == "SHAR":
#                 subgraphs = shar(densities, G, density_threshold=dens_threshold, dist_threshold=dist_threshold)
#                 if not subgraphs:
#                     st.warning("Nenhum hotspot foi gerado com o algoritmo SHAR. Verifique os parâmetros.")
#                 else:
#                     m_shar = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
#                                                   gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
#                     edges_4326 = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index().to_crs(epsg=4326)
#                     color_list = ["red", "green", "blue", "purple", "orange", "yellow"]
#                     from shapely.geometry import LineString
#                     for cid, edge_pairs in subgraphs:
#                         color = color_list[cid % len(color_list)]
#                         for (u, v) in edge_pairs:
#                             mask_uv = ((edges_4326['u'] == u) & (edges_4326['v'] == v)) | ((edges_4326['u'] == v) & (edges_4326['v'] == u))
#                             row_ = edges_4326[mask_uv]
#                             if not row_.empty:
#                                 line = row_.iloc[0].geometry
#                                 if isinstance(line, LineString):
#                                     coords = [(pt[1], pt[0]) for pt in line.coords]
#                                     folium.PolyLine(coords, color=color, weight=3, tooltip=f"Cluster {cid}").add_to(m_shar)
#                     st.subheader("Mapa SHAR (Subgraphs)")
#                     st_folium(m_shar, width=700, height=500)
                    
#                     df_table = build_cluster_table_subgraphs(subgraphs, G)
#                     st.subheader("Tabela de Clusters (SHAR)")
#                     show_cluster_table_as_links(df_table)
                    
#             elif alg_option == "Expansive Network":
#                 expansions = expansive_network(densities, G, density_threshold=dens_threshold)
#                 if not expansions:
#                     st.warning("Nenhum hotspot foi gerado com o algoritmo Expansive Network. Verifique os parâmetros.")
#                 else:
#                     m_exp = folium.Map(location=[gdf_crime.to_crs(epsg=4326).geometry.y.mean(),
#                                                  gdf_crime.to_crs(epsg=4326).geometry.x.mean()], zoom_start=12)
#                     edges_4326 = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index().to_crs(epsg=4326)
#                     color_list = ["red", "green", "blue", "purple", "orange", "yellow"]
#                     from shapely.geometry import LineString
#                     for c_id, node_set, edge_pairs in expansions:
#                         color = color_list[c_id % len(color_list)]
#                         for (u, v) in edge_pairs:
#                             mask_uv = ((edges_4326['u'] == u) & (edges_4326['v'] == v)) | ((edges_4326['u'] == v) & (edges_4326['v'] == u))
#                             row_ = edges_4326[mask_uv]
#                             if not row_.empty:
#                                 line = row_.iloc[0].geometry
#                                 if isinstance(line, LineString):
#                                     coords = [(pt[1], pt[0]) for pt in line.coords]
#                                     folium.PolyLine(coords, color=color, weight=3, tooltip=f"Cluster {c_id}").add_to(m_exp)
#                     st.subheader("Mapa Expansive Network")
#                     st_folium(m_exp, width=700, height=500)
                    
#                     df_table = build_cluster_table_subgraphs(expansions, G)
#                     st.subheader("Tabela de Clusters (Expansive Network)")
#                     show_cluster_table_as_links(df_table)
#         else:
#             st.warning("Nenhum MUNICÍPIO selecionado ou rede indisponível. Não foi possível gerar hotspots baseados na rede. Exibindo apenas os pontos.")
#             center_lat = gdf_crime.to_crs(epsg=4326).geometry.y.mean()
#             center_lon = gdf_crime.to_crs(epsg=4326).geometry.x.mean()
#             m_ = folium.Map(location=[center_lat, center_lon], zoom_start=12)
#             MarkerCluster().add_to(m_)
#             for _, row in gdf_crime.to_crs(epsg=4326).iterrows():
#                 folium.Marker(location=[row.geometry.y, row.geometry.x]).add_to(m_)
#             st_folium(m_, width=700, height=500)
        
#         if st.button("Exportar hotspots como shapefile"):
#             try:
#                 gdf_crime.to_file("hotspots_resultantes.shp")
#                 st.success("Arquivo exportado como 'hotspots_resultantes.shp'")
#             except Exception as e:
#                 st.error(f"Erro na exportação: {e}")
#     else:
#         st.warning("Carregue um arquivo CSV para iniciar.")

# if __name__ == "__main__":
#     main()
