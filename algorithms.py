# algorithms.py
import numpy as np
from shapely.geometry import MultiPoint
from sklearn.cluster import AgglomerativeClustering

def phar(densities, G, density_threshold=1.0, dist_threshold=300):
    """
    PHAR: Seleciona nós com densidade acima do limiar, clusteriza-os e gera polígonos (convex hull).
    """
    selected_nodes = [n for n, d in densities.items() if d >= density_threshold]
    if not selected_nodes:
        return []
    import osmnx as ox
    nodes_gdf = ox.graph_to_gdfs(G, nodes=True, edges=False).to_crs(epsg=3857)
    sub_nodes = nodes_gdf.loc[selected_nodes]
    coords = np.vstack([sub_nodes.geometry.x, sub_nodes.geometry.y]).T
    if len(coords) < 2:
        return []
    cluster_model = AgglomerativeClustering(n_clusters=None, distance_threshold=dist_threshold, linkage='average')
    labels = cluster_model.fit_predict(coords)
    sub_nodes['cluster'] = labels
    polygons = []
    for c_id in np.unique(labels):
        group = sub_nodes[sub_nodes['cluster'] == c_id]
        if len(group) < 3:
            continue
        points = MultiPoint(list(group.geometry))
        hull = points.convex_hull
        polygons.append((c_id, hull))
    return polygons

def i_phar(densities, G, old_polygons, new_crimes, bandwidth=200, density_threshold=1.0, dist_threshold=300):
    """
    i-PHAR: Atualiza as densidades com novas ocorrências e reaplica a lógica do PHAR.
    Trata corretamente o CRS dos novos crimes.
    """
    import geopandas as gpd
    # Se new_crimes já tem CRS, converta para EPSG:3857; caso contrário, defina-o.
    if hasattr(new_crimes, 'crs'):
        new_crimes = new_crimes.to_crs("EPSG:3857")
    else:
        new_crimes = gpd.GeoSeries(new_crimes).set_crs("EPSG:3857", allow_override=True)
    gdf_new = gpd.GeoDataFrame(geometry=new_crimes)
    crime_coords = [(geom.x, geom.y) for geom in gdf_new.geometry]
    import osmnx as ox
    for (cx, cy) in crime_coords:
        nearest_node = ox.distance.nearest_nodes(G, X=[cx], Y=[cy])[0]
        visited = set()
        queue = [(nearest_node, 0)]
        while queue:
            current, dist = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            decay = np.exp(-dist / bandwidth)
            densities[current] += decay
            for neighbor in G[current]:
                edge_length = G[current][neighbor][0].get('length', 1)
                ndist = dist + edge_length
                if ndist <= bandwidth:
                    queue.append((neighbor, ndist))
    return phar(densities, G, density_threshold, dist_threshold)

def shar(densities, G, density_threshold=1.0, dist_threshold=300):
    """
    SHAR: Seleciona nós com densidade >= threshold, clusteriza-os e constrói subgrafos
    conectando os nós do cluster via caminhos mínimos.
    """
    selected_nodes = [n for n, d in densities.items() if d >= density_threshold]
    if not selected_nodes:
        return []
    import osmnx as ox
    nodes_gdf = ox.graph_to_gdfs(G, nodes=True, edges=False).to_crs(epsg=3857)
    sub_nodes = nodes_gdf.loc[selected_nodes]
    coords = np.vstack([sub_nodes.geometry.x, sub_nodes.geometry.y]).T
    if len(coords) < 2:
        return []
    cluster_model = AgglomerativeClustering(n_clusters=None, distance_threshold=dist_threshold, linkage='average')
    labels = cluster_model.fit_predict(coords)
    sub_nodes['cluster'] = labels
    subgraphs = []
    for c_id in np.unique(labels):
        group = sub_nodes[sub_nodes['cluster'] == c_id]
        if len(group) < 2:
            continue
        c_nodes = list(group.index)
        edges_in_subgraph = []
        for i in range(len(c_nodes)):
            for j in range(i+1, len(c_nodes)):
                try:
                    path = ox.shortest_path(G, c_nodes[i], c_nodes[j])
                    path_pairs = list(zip(path[:-1], path[1:]))
                    edges_in_subgraph.extend(path_pairs)
                except Exception:
                    pass
        subgraphs.append((c_id, set(edges_in_subgraph)))
    return subgraphs

def expansive_network(densities, G, density_threshold=1.0):
    """
    Expansive Network: Expande a partir dos nós com maior densidade para formar clusters.
    """
    sorted_nodes = sorted(densities.items(), key=lambda x: x[1], reverse=True)
    visited = set()
    expansions = []
    c_id = 0
    for n, dval in sorted_nodes:
        if n in visited:
            continue
        if dval < density_threshold:
            break
        frontier = [n]
        cluster_edges = []
        cluster_nodes = set()
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            cluster_nodes.add(current)
            for neighbor in G[current]:
                if densities.get(neighbor, 0) >= density_threshold and neighbor not in visited:
                    frontier.append(neighbor)
                cluster_edges.append((current, neighbor))
        expansions.append((c_id, cluster_nodes, cluster_edges))
        c_id += 1
    return expansions
