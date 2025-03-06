import streamlit as st
import pandas as pd
from utils.data_processing import validate_and_clean_data
from utils.kde_analysis import generate_kde_map
from utils.visualization import plot_statistics
from utils.logger import setup_logger, log_message

# Configuração inicial do Streamlit
st.set_page_config(page_title="Crime Hotspot Analysis", layout="wide")

# Configurar o logger globalmente
setup_logger()

# Carregar dados originais na sessão, se ainda não existirem
if "original_data" not in st.session_state:
    st.session_state.original_data = None

# Sidebar para upload e filtros
st.sidebar.title("Upload e Filtros")
uploaded_file = st.sidebar.file_uploader("Carregar arquivo CSV", type=["csv"])

if uploaded_file:
    # Caso seja o primeiro carregamento, processa o arquivo
    if st.session_state.original_data is None:
        try:
            raw_data = pd.read_csv(uploaded_file, sep=";", encoding="utf-8")
            log_message(f"Arquivo CSV carregado com sucesso: {uploaded_file.name}", level="info", file_name=uploaded_file.name, function_name="upload_and_validate_data")
            data = validate_and_clean_data(raw_data, file_name=uploaded_file.name)
            log_message("Dados validados e limpos com sucesso.", level="info", file_name=uploaded_file.name, function_name="upload_and_validate_data")
            st.sidebar.success("Dados carregados e validados com sucesso!")
            st.session_state.original_data = data.copy()
        except Exception as e:
            log_message(f"Erro ao processar os dados do arquivo: {uploaded_file.name}. Erro: {e}", level="error", file_name=uploaded_file.name, function_name="upload_and_validate_data")
            st.sidebar.error(f"Erro ao carregar os dados: {e}")
            st.stop()

    original_data = st.session_state.original_data
    # Inicia o dataset filtrado a partir do original
    filtered_data = original_data.copy()

    # Filtros temporais
    st.sidebar.subheader("Filtros Temporais")
    date_range = st.sidebar.date_input("Selecione o intervalo de datas", [])
    if date_range and len(date_range) == 2:
        filtered_data = filtered_data[
            (filtered_data["DATA_FATO"] >= str(date_range[0])) &
            (filtered_data["DATA_FATO"] <= str(date_range[1]))
        ]
        log_message(f"Filtro de datas aplicado: {date_range[0]} a {date_range[1]}", level="info", function_name="apply_date_filter")

    # Filtros geográficos interdependentes
    st.sidebar.subheader("Filtros Geográficos")
    # Atualiza as opções de município com base no dataset filtrado até o momento
    municipio_options = sorted(filtered_data["MUNICIPIO"].unique())
    municipio_filter = st.sidebar.multiselect("Município", options=municipio_options)
    if municipio_filter:
        filtered_data = filtered_data[filtered_data["MUNICIPIO"].isin(municipio_filter)]
        log_message(f"Filtro de municípios aplicado: {', '.join(municipio_filter)}", level="info", function_name="apply_municipio_filter")

    # Atualiza as opções de bairro com base no dataset já filtrado
    bairro_options = sorted(filtered_data["BAIRRO"].unique())
    bairro_filter = st.sidebar.multiselect("Bairro", options=bairro_options)
    if bairro_filter:
        filtered_data = filtered_data[filtered_data["BAIRRO"].isin(bairro_filter)]
        log_message(f"Filtro de bairros aplicado: {', '.join(bairro_filter)}", level="info", function_name="apply_bairro_filter")

    # Filtro por tipo de crime
    st.sidebar.subheader("Filtros por Tipo de Crime")
    crime_type_options = sorted(filtered_data["DESCR_NATUREZA_PRINCIPAL"].unique())
    crime_type_filter = st.sidebar.multiselect("Tipo de Crime", options=crime_type_options)
    if crime_type_filter:
        filtered_data = filtered_data[filtered_data["DESCR_NATUREZA_PRINCIPAL"].isin(crime_type_filter)]
        log_message(f"Filtro de tipos de crimes aplicado: {', '.join(crime_type_filter)}", level="info", function_name="apply_crime_type_filter")

    # Filtros por faixa horária
    st.sidebar.subheader("Filtros por Faixa Horária")
    # Para as faixas, usamos o conjunto original para garantir todas as opções
    fxh1_options = sorted(original_data["FAIXA_HORA_1"].dropna().unique())
    fxh1_filter = st.sidebar.multiselect("Filtrar por Faixa de 1 Hora", options=fxh1_options)
    if fxh1_filter:
        filtered_data = filtered_data[filtered_data["FAIXA_HORA_1"].isin(fxh1_filter)]
        log_message(f"Filtro de Faixa de 1 Hora aplicado: {', '.join(map(str, fxh1_filter))}", level="info", function_name="apply_fxh1_filter")

    fxh6_options = sorted(original_data["FAIXA_HORA_6"].dropna().unique())
    fxh6_filter = st.sidebar.multiselect("Filtrar por Faixa de 6 Horas", options=fxh6_options)
    if fxh6_filter:
        filtered_data = filtered_data[filtered_data["FAIXA_HORA_6"].isin(fxh6_filter)]
        log_message(f"Filtro de Faixa de 6 Horas aplicado: {', '.join(map(str, fxh6_filter))}", level="info", function_name="apply_fxh6_filter")

    # Não é mais necessário um botão de "remover filtros", pois os filtros são aplicados diretamente
    if filtered_data.empty:
        st.warning("Nenhum dado disponível após a aplicação dos filtros.")
        log_message("Nenhum dado disponível após a aplicação dos filtros.", level="warning", function_name="check_filtered_data")
    else:
        # Visualização dos resultados
        st.title("Mapa de Hotspots Criminais")
        kde_map = generate_kde_map(filtered_data)
        st.components.v1.html(kde_map._repr_html_(), height=600)

        st.title("Estatísticas Resumidas")
        plot_statistics(filtered_data)
else:
    st.info("Por favor, carregue um arquivo CSV para começar.")
