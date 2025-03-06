# network_utils.py
import osmnx as ox
import numpy as np

def get_osmnx_graph(region_query):
    """
    Obtém a rede viária via OSMnx para a região especificada e projeta para EPSG:3857.
    """
    G = ox.graph_from_place(region_query, network_type='drive')
    G = ox.project_graph(G, to_crs='epsg:3857')
    return G

def snap_points_to_network(gdf, G):
    """
    'Snap' dos pontos de crime aos nós da rede viária, convertendo para EPSG:3857.
    """
    gdf = gdf.to_crs(epsg=3857)
    x_coords = gdf.geometry.x.values
    y_coords = gdf.geometry.y.values
    nearest_node_ids = ox.distance.nearest_nodes(G, X=x_coords, Y=y_coords)
    gdf['nearest_node'] = nearest_node_ids
    return gdf

def compute_node_densities(gdf_crimes, G, bandwidth=200):
    """
    Implementa uma versão simplificada de KDE restrito à rede.
    Para cada nó, soma contribuições dos crimes com decaimento exponencial.
    """
    densities = {node: 0.0 for node in G.nodes()}
    gdf_crimes = gdf_crimes.to_crs(epsg=3857)
    crime_coords = [(geom.x, geom.y) for geom in gdf_crimes.geometry]
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
    return densities
