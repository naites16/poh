# cluster_table.py
import pandas as pd
import streamlit as st
from pyproj import Transformer

def generate_google_maps_link(cluster_points):
    """
    Gera um link do Google Maps para a rota passando pelos pontos do cluster.
    cluster_points: lista de tuplas (lat, lon) em EPSG:4326.
    """
    if not cluster_points:
        return None
    base_url = "https://www.google.com/maps/dir/?api=1"
    origin = cluster_points[0]
    destination = cluster_points[-1]
    waypoints = cluster_points[1:-1]
    max_waypoints = 23  # 1 origem + 23 waypoints + 1 destino = 25 pontos
    if len(waypoints) > max_waypoints:
        waypoints = waypoints[:max_waypoints]
    origin_str = f"{origin[0]},{origin[1]}"
    destination_str = f"{destination[0]},{destination[1]}"
    waypoints_str = "|".join([f"{lat},{lon}" for lat, lon in waypoints])
    link = f"{base_url}&origin={origin_str}&destination={destination_str}"
    if waypoints_str:
        link += f"&waypoints={waypoints_str}"
    return link

def build_cluster_table_polygons(poly_list):
    """
    poly_list: lista de tuplas (cluster_id, polygon) onde o polígono está em EPSG:4326.
    Gera uma tabela com o número do cluster, quantidade de vértices e link para o Google Maps.
    """
    rows = []
    for cid, poly in poly_list:
        if poly.geom_type == 'Polygon':
            coords = list(poly.exterior.coords)
        else:
            coords = list(poly.convex_hull.exterior.coords)
        # Converter de (lon, lat) para (lat, lon)
        cluster_points = [(lat, lon) for lon, lat in coords]
        link = generate_google_maps_link(cluster_points[:25])
        rows.append({
            "Cluster": cid,
            "Qtd. Pontos": len(coords),
            "Rota Google Maps": link
        })
    return pd.DataFrame(rows)

def build_cluster_table_subgraphs(subgraphs, G):
    """
    subgraphs: lista de tuplas (cluster_id, nodes, edges) ou (cluster_id, edges)
    G: grafo original, cujas coordenadas estão em EPSG:3857.
    Converte os nós para EPSG:4326 para gerar o link.
    """
    rows = []
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    for item in subgraphs:
        if len(item) == 2:
            cid, edge_pairs = item
            node_set = set()
            for (u, v) in edge_pairs:
                node_set.add(u)
                node_set.add(v)
        else:
            cid, node_set, edge_pairs = item
        cluster_points = []
        for n in node_set:
            # G.nodes[n]['x'] e G.nodes[n]['y'] estão em EPSG:3857; converter para 4326:
            x, y = G.nodes[n].get('x', None), G.nodes[n].get('y', None)
            if x is None or y is None:
                continue
            lon, lat = transformer.transform(x, y)
            cluster_points.append((lat, lon))
        # Ordena os pontos para consistência
        cluster_points = sorted(cluster_points, key=lambda pt: (pt[0], pt[1]))
        link = generate_google_maps_link(cluster_points)
        rows.append({
            "Cluster": cid,
            "Qtd. Pontos": len(node_set),
            "Rota Google Maps": link
        })
    return pd.DataFrame(rows)

def show_cluster_table_as_links(df_cluster_table):
    table_html = "<table style='width:100%; border-collapse: collapse;'><thead><tr style='background-color: #f2f2f2;'><th style='border: 1px solid #ddd; padding: 8px;'>Cluster</th><th style='border: 1px solid #ddd; padding: 8px;'>Qtd. Pontos</th><th style='border: 1px solid #ddd; padding: 8px;'>Rota Google Maps</th></tr></thead><tbody>"
    for _, row in df_cluster_table.iterrows():
        link_html = f'<a href="{row["Rota Google Maps"]}" target="_blank">Abrir Rota</a>' if row["Rota Google Maps"] else "-"
        table_html += f"<tr><td style='border: 1px solid #ddd; padding: 8px;'>{row['Cluster']}</td><td style='border: 1px solid #ddd; padding: 8px;'>{row['Qtd. Pontos']}</td><td style='border: 1px solid #ddd; padding: 8px;'>{link_html}</td></tr>"
    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)


# # cluster_table.py
# import streamlit as st
# import pandas as pd

# def generate_google_maps_link(cluster_points):
#     """
#     Gera um link do Google Maps para a rota passando pelos pontos do cluster.
#     cluster_points: lista de tuplas (lat, lon) em EPSG:4326.
#     """
#     if not cluster_points:
#         return None
#     base_url = "https://www.google.com/maps/dir/?api=1"
#     origin = cluster_points[0]
#     destination = cluster_points[-1]
#     waypoints = cluster_points[1:-1]
#     max_waypoints = 23
#     if len(waypoints) > max_waypoints:
#         waypoints = waypoints[:max_waypoints]
#     origin_str = f"{origin[0]},{origin[1]}"
#     destination_str = f"{destination[0]},{destination[1]}"
#     waypoints_str = "|".join([f"{lat},{lon}" for lat, lon in waypoints])
#     link = f"{base_url}&origin={origin_str}&destination={destination_str}"
#     if waypoints_str:
#         link += f"&waypoints={waypoints_str}"
#     return link

# def build_cluster_table_polygons(poly_list):
#     """
#     poly_list: lista de tuplas (cluster_id, polygon) onde o polígono está em EPSG:4326.
#     """
#     rows = []
#     for cid, poly in poly_list:
#         if poly.geom_type == 'Polygon':
#             coords = list(poly.exterior.coords)
#         else:
#             coords = list(poly.convex_hull.exterior.coords)
#         # Converter de (lon, lat) para (lat, lon)
#         cluster_points = [(lat, lon) for lon, lat in coords]
#         link = generate_google_maps_link(cluster_points)
#         rows.append({
#             "Cluster": cid,
#             "Qtd. Pontos": len(coords),
#             "Rota Google Maps": link
#         })
#     return pd.DataFrame(rows)

# def build_cluster_table_subgraphs(subgraphs, G):
#     """
#     subgraphs: lista de tuplas (cluster_id, nodes, edges) ou (cluster_id, edges)
#     G: grafo original (assumido com nós com atributos 'x' e 'y' em WGS84).
#     """
#     rows = []
#     for item in subgraphs:
#         if len(item) == 2:
#             cid, edge_pairs = item
#             node_set = set()
#             for (u, v) in edge_pairs:
#                 node_set.add(u)
#                 node_set.add(v)
#         else:
#             cid, node_set, edge_pairs = item
#         cluster_points = []
#         for n in node_set:
#             lat = G.nodes[n].get('y', 0)
#             lon = G.nodes[n].get('x', 0)
#             cluster_points.append((lat, lon))
#         cluster_points = sorted(cluster_points, key=lambda x: (x[0], x[1]))
#         link = generate_google_maps_link(cluster_points)
#         rows.append({
#             "Cluster": cid,
#             "Qtd. Pontos": len(node_set),
#             "Rota Google Maps": link
#         })
#     return pd.DataFrame(rows)

# def show_cluster_table_as_links(df_cluster_table):
#     table_html = "<table><thead><tr><th>Cluster</th><th>Qtd. Pontos</th><th>Rota Google Maps</th></tr></thead><tbody>"
#     for _, row in df_cluster_table.iterrows():
#         link_html = f'<a href="{row["Rota Google Maps"]}" target="_blank">Abrir Rota</a>' if row["Rota Google Maps"] else "-"
#         table_html += f"<tr><td>{row['Cluster']}</td><td>{row['Qtd. Pontos']}</td><td>{link_html}</td></tr>"
#     table_html += "</tbody></table>"
#     st.markdown(table_html, unsafe_allow_html=True)
