import geopandas as gpd
from shapely.geometry import mapping, Point
import pandas as pd
import streamlit as st
import json
import folium
from folium import GeoJsonTooltip, Map, MacroElement
from folium.features import DivIcon
from branca.element import MacroElement, Template
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, Draw, MeasureControl, Geocoder, TagFilterButton
import streamlit.components.v1 as components
from io import BytesIO
from jinja2 import Template

#----CONFIG----#
st.set_page_config(layout="wide")
st.title("GeoARBO")
#--------------#

#----CAMINHO----#
CAMINHO_CASOS = "Shapes/CASOS/CASOS.shp"
CAMINHO_CRS = "Shapes/crs.shp"
CAMINHO_UVIS = "Shapes/uvis.shp"
CAMINHO_QUADRAS = "Shapes/QDRsiscoz_antigas.shp"
CAMINHO_BCC = "Shapes/Bloqueios/BCC.shp"
CAMINHO_BCN = "Shapes/Bloqueios/BCN.shp"
CAMINHO_TCD = "Shapes/Bloqueios/TCD.shp"
#---------------#

#----ESTILOS DE POLÍGONO FOLIUM----#
def style_function_crs(feature):
    return {"fillOpacity": 0.0, "color": "black", "weight": 4, 'opacity': 0.3}

def style_function_uvis(feature):
    return {"fillOpacity": 0.0, "color": "blue", "weight": 3, 'opacity': 0.3}

def style_function_quadras(feature):
    return {"fillOpacity": 0.0, "color": "black", "weight": 1.5}

def style_function_bcc(feature):
    valor = feature['properties'].get('CATEG')
    if valor == "2":
        return { 'fillColor': 'black', 'color': 'red', 'weight':2, 'fillOpacity': 0.0 }
    elif valor == "4":
        return { 'fillColor': 'black', 'color' : 'green', 'weight' : 2, 'fillOpacity': 0.0 }
    else:
        return {"fillOpacity": 0.0, "color": "black", "weight": 1.5}
    
def style_function_bcn(feature):
    return {"fillOpacity": 0.6, "color": "yellow", "weight": 1.5, 'opacity': 0.3}

def style_function_tcd(feature):
    valor = feature['properties'].get('CATEG')
    if valor == "2":
        return { 'fillColor': 'black', 'color': 'purple', 'weight':2 , 'fillOpacity': 0.0 }
    elif valor == "4":
        return { 'fillColor': 'black', 'color' : 'lightgreen', 'weight' : 2, 'fillOpacity': 0.0 }
    else:
        return {"fillOpacity": 0.0, "color": "black", "weight": 1.5}

#----CARREGAR DADOS (CACHE)----#
def carregar_dados(caminho_casos, caminho_uvis, caminho_crs, caminho_quadras, caminho_bcc, caminho_bcn, caminho_tcd):

    casos = gpd.read_file(caminho_casos).to_crs(epsg=4326)   
    uvis = gpd.read_file(caminho_uvis).to_crs(epsg=4326)
    crs = gpd.read_file(caminho_crs).to_crs(epsg=4326)
    quadras = gpd.read_file(caminho_quadras).to_crs(epsg=4326)
    bcc = gpd.read_file(caminho_bcc).to_crs(epsg=4326)
    bcn = gpd.read_file(caminho_bcn).to_crs(epsg=4326)
    tcd = gpd.read_file(caminho_tcd).to_crs(epsg=4326)

    #Tipo das datas
    if "DT_NOTIFIC" in casos.columns:
        casos["DT_NOTIFIC"] = pd.to_datetime(casos["DT_NOTIFIC"], errors="coerce")
    if "DT_SIN_PRI" in casos.columns:
        casos["DT_SIN_PRI"] = pd.to_datetime(casos["DT_SIN_PRI"], errors="coerce")

    #Filtrar confirmado e remover NAs
    if "CLASSI_FIN" in casos.columns:
        casos = casos[casos["CLASSI_FIN"] == "confirmado"].copy()
    if "DT_NOTIFIC" in casos.columns:
        casos = casos.dropna(subset=["DT_NOTIFIC"])

    #SE para inteiro
    casos['SE'] = pd.to_numeric(casos['SE'], errors='coerce')
    bcc['SE'] = pd.to_numeric(bcc['SE'], errors='coerce')
    bcn['SE'] = pd.to_numeric(bcn['SE'], errors='coerce')
    tcd['SE'] = pd.to_numeric(tcd['SE'], errors='coerce')

    #TIPO no tcd
    if 'TIPO' not in tcd.columns:
        tcd['TIPO'] = 'TCD'

    #Forçar geometria válida
    casos = casos[casos.geometry.notnull()].copy()
    casos.reset_index(drop=True, inplace=True)

    quadras = quadras[quadras.geometry.notnull()].copy()
    quadras.reset_index(drop=True, inplace=True)

    return casos, uvis, crs, quadras, bcc, bcn, tcd
#--------------------------------#

#----FUNÇÃO PARA FILTRAR CASOS NO CACHE----#
@st.cache_data
def filtrar_casos(_casos_df, semanas_tuple, uvis_tuple):
    if not semanas_tuple or not uvis_tuple:
        return _casos_df.iloc[0:0].copy()

    mask = _casos_df["SE"].isin(semanas_tuple) & _casos_df["SUVIS"].isin(uvis_tuple)
    return _casos_df.loc[mask].copy()

#----FILTRAR QUADRAS----#
@st.cache_data
def filtrar_quadras(_quadras, uvis_tuple):
    if not uvis_tuple:
        return _quadras.iloc[0:0].copy()
    
    mask_quadra = _quadras["SUVIS"].isin(uvis_tuple)
    return _quadras.loc[mask_quadra].copy()

#----FILTRAR SEMANA----#
@st.cache_data
def filtrar_bcc(_gdf, semanas_tuple):
    if not semanas_tuple:
        return _gdf.iloc[0:0].copy()
                
    mask = _gdf['SE'].isin(semanas_tuple)
    return _gdf.loc[mask].copy()

def filtrar_bcn(_gdf, semanas_tuple):
    if not semanas_tuple:
        return _gdf.iloc[0:0].copy()
                
    mask = _gdf['SE'].isin(semanas_tuple)
    return _gdf.loc[mask].copy()

def filtrar_tcd(_gdf, semanas_tuple):
    if not semanas_tuple:
        return _gdf.iloc[0:0].copy()
                
    mask = _gdf['SE'].isin(semanas_tuple)
    return _gdf.loc[mask].copy()
#-------------------------------------------#

#----LISTA DE PONTOS----#
def preparar_pontos_para_cluster(casos_filtrados):
    pontos = []
    coords = [(geom.y, geom.x) for geom in casos_filtrados.geometry]
    #Popups
    for (lat, lon), (_, row) in zip(coords, casos_filtrados.iterrows()):
        dt_not = row["DT_NOTIFIC"]
        dt_text = dt_not.strftime("%d/%m/%Y") if pd.notna(dt_not) else "N/A"
        popup_texto = (
            f"<b>N ficha:</b> {row.get('NU_NOTIFIC', 'N/A')}<br>"
            f"<b>SINAN:</b> {row.get('ID_AGRAVO', 'N/A')}<br>"
            f"<b>Data Notificação:</b> {dt_text}<br>"
            f"<b>Semana (SE):</b> {row.get('SE', 'N/A')}<br><br>"
            f"<b>CRS:</b> {row.get('CRS', 'N/A')}<br>"
            f"<b>UVIS:</b> {row.get('SUVIS', 'N/A')}<br>"
            f"<b>DA:</b> {row.get('NOME_DISTR', 'N/A')}<br><br>"
            f"<b>Nome:</b> {row.get('NM_PACIENT', 'N/A')}<br>"
            f"<b>Endereço:</b> {row.get('NM_LOGRADO', 'N/A')}<br>"
            f"<b>Número:</b> {row.get('NU_NUMERO', 'N/A')}<br>"
            f"<b>CEP:</b> {row.get('NU_CEP', 'N/A')}<br>"
        )
        tag_agravo = row.get('ID_AGRAVO', 'N/A')
        pontos.append([lat, lon, popup_texto, tag_agravo])
    return pontos
#----------------------#

#----GERAR MAPAS----#
def criar_mapa_html(pontos, uvis_gdf, crs_gdf, quadras_gdf, buffer_gdf = None, bcc_gdf = None, bcn_gdf = None, tcd_gdf=None, center_lat=-23.5505, center_lon=-46.6333, zoom_start=12):

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="OpenStreetMap"
    )
    
    #Cores dos agravos
    paleta_agravos = {
        'dengue' : '#E60000',
        'chikungunya' : '#0052CC',
        'zika_virus': '#FF8C00',
        'oropouche' : '#8A2BE2'
    }

    #Cluster (Pontos)
    marker_cluster = MarkerCluster(name="Casos", options={"disableClusteringAtZoom": 11}).add_to(m)
    for lat, lon, popup_html, tag in pontos:
        cor_marcador = paleta_agravos.get(str(tag))
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,               
            color=cor_marcador,        
            fill=True,
            fill_color=cor_marcador,  
            fill_opacity=1,
            weight=1,
            popup=popup_html,
            tags=[str(tag)]
        ).add_to(marker_cluster)

    #Buffer
    if buffer_gdf is not None and not buffer_gdf.empty:
        style_buffer = lambda x: {
            'fillColor': 'red',
            'color': 'blue',
            'weight': 2,
            'fillOpacity' : 0.0
        }     
        folium.GeoJson(
            buffer_gdf,
            style_function=style_buffer,
            name= "Buffer 150m (Casos)",
            show=False
        ).add_to(m)

    #Camadas de polígonos
    folium.GeoJson(uvis_gdf, style_function=style_function_uvis, name="UVIS").add_to(m)
    folium.GeoJson(crs_gdf, style_function=style_function_crs, name="CRS", show=False).add_to(m)
    
    #Quadras     
    folium.GeoJson(
        quadras_gdf,
        style_function=style_function_quadras,
        name="Quadras (Polígonos)",
        popup=folium.GeoJsonPopup(fields=['CODQUADRA', 'SUVIS']),
        show=False
    ).add_to(m)

    #Bloqueios
    if bcc_gdf is not None and not bcc_gdf.empty:
        folium.GeoJson(
                bcc_gdf,
                style_function=style_function_bcc,
                name='Bloqueio de Criadouro',
                popup=folium.GeoJsonPopup(fields=['CATEG','TIPO','SE']),
                show=False
        ).add_to(m)

    if bcn_gdf is not None and not bcn_gdf.empty:
        folium.GeoJson(
                bcn_gdf,
                style_function=style_function_bcn,
                name='Bloqueio de Nebulização',
                popup=folium.GeoJsonPopup(fields=['TIPO','SE']),
                show=False
        ).add_to(m)       

    if tcd_gdf is not None and not tcd_gdf.empty:
        folium.GeoJson(
                tcd_gdf,
                style_function=style_function_tcd,
                name='Todos Contra a Dengue', 
                popup=folium.GeoJsonPopup(fields=['CATEG','TIPO','SE']),
                show=False
        ).add_to(m)

    #Rótulos das quadras
    try:
        rotulos_layer = folium.FeatureGroup(
            name="Rótulos das Quadras (Ligar/Desligar)",
            show=False
        ).add_to(m)

        quadras_rotulos = quadras_gdf.copy()
        quadras_rotulos.geometry = quadras_rotulos.geometry.representative_point()

        for _, row in quadras_rotulos.iterrows():
            codquadra = row['CODQUADRA']
            pos = (row.geometry.y, row.geometry.x)
            icon_html = f"""
            <div style="font-size:11px; color:black; font-weight:bold;
            text-shadow:0 0 2px white, 0 0 3px white;
            transform: translate(-60%,0);
            white-space: nowrap;">
            {codquadra}
            </div>
            """
            icon = DivIcon(html=icon_html)
            folium.Marker(location=pos, icon=icon).add_to(rotulos_layer)

    except Exception as e:
        st.warning(f"Não foi possível gerar os rótulos das quadras. Erro: {e}")
    
    #Ferramenta de desenho
    draw_options = {
            'polyline':{'shapeOptions':{'color':'blue'}},
            'polygon': {'shapeOptions':{'color':'blue'}},
            'rectangle':False,
            'circle':False,
            'marker':{'shapeOptions':{'color':'blue'}},
            'circlemarker':False
        }
    draw = Draw(
        export = False,
        draw_options=draw_options,
        edit_options={
            'edit': False,
            'remove':True
        }
    )
    draw.add_to(m)

    #Ferramenta de Régua
    MeasureControl(
        position='topleft',
        primary_length_unit='kilometers',
        secondary_length_unit='meters',
        primary_area_unit='sqmeters',
        secondary_area_unit=None,
        active_color='#000000',          
        completed_color='#000000'  
    ).add_to(m)

    #Barra de pesquisa
    Geocoder(
        position='topright',
        collapsed=True
    ).add_to(m)

    #Filtro
    try:
        tags_unicas = sorted(list(set([p[3] for p in pontos])))
    except IndexError:
        tags_unicas = []
    
    if tags_unicas:
        TagFilterButton(
        data=tags_unicas,
        position='topleft'
    ).add_to(m)

    folium.LayerControl().add_to(m)
    return m.get_root().render()
#--------------------------------#

#----INTERFACE & LÓGICA DE GERAÇÃO----#
try:
    casos, uvis, crs, quadras, bcc, bcn, tcd = carregar_dados(CAMINHO_CASOS, CAMINHO_UVIS, CAMINHO_CRS, CAMINHO_QUADRAS, CAMINHO_BCC, CAMINHO_BCN, CAMINHO_TCD)

    st.subheader("Período:")

    #Opções para filtro
    uvis_disp = sorted(casos["SUVIS"].unique())
    se_disp = sorted(casos["SE"].unique())

    #Widgets de seleção
    uvis_selecionada = st.multiselect("UVIS:", uvis_disp)
    se_selecionada = st.multiselect("Semana Epidemiológica:", se_disp)

    #Botão para gerar o mapa
    if st.button("Gerar mapa", type="primary"):
        if not se_selecionada:
            st.warning("Selecione uma semana.")
        elif not uvis_selecionada:
            st.warning("Selecione uma UVIS.")
        else:
            #Salvar filtros atuais em session_state (CACHE)
            st.session_state["last_filters"] = (tuple(sorted(se_selecionada)), tuple(sorted(map(str, uvis_selecionada))))
            #Marcar que é necessário (re)gerar
            st.session_state["map_needs_update"] = True

    #Se o usuário já gerou um mapa, mostramos o resultado salvo se filtros não mudaram
    filtros_atuais = (tuple(sorted(se_selecionada)) if se_selecionada else tuple(),
                      tuple(sorted(map(str, uvis_selecionada))) if uvis_selecionada else tuple())

    #Decidir se devemos (re)gerar
    need_generate = st.session_state.get("map_needs_update", False) or (st.session_state.get("last_filters") != filtros_atuais)

    if st.session_state.get("last_filters") is None and not need_generate:
        st.info("Escolha filtros e clique em 'Gerar mapa' para visualizar.")
    else:
        if st.session_state.get("last_filters") != filtros_atuais:
            st.session_state["last_filters"] = filtros_atuais

        #Se o mapa precisa ser (re)gerado:
        if st.session_state.get("map_needs_update", False):
            #Filtrar casos via função cacheada
            semanas_tuple, uvis_tuple = st.session_state["last_filters"]
            casos_filtrados = filtrar_casos(casos, semanas_tuple, uvis_tuple)
            quadras_filtradas = filtrar_quadras(quadras, uvis_tuple)

            #Filtrar semana via função cacheada
            bcc_filtrado_full = filtrar_bcc(bcc, semanas_tuple)
            bcn_filtrado_full = filtrar_bcn(bcn, semanas_tuple)
            tcd_filtrado_full = filtrar_tcd(tcd, semanas_tuple)   

            colunas_bloqueios_bcc = ['geometry','CATEG','TIPO','SE']
            colunas_bloqueios_bcn = ['geometry','TIPO','SE']
            colunas_bloqueios_tcd = ['geometry','CATEG','TIPO','SE']

            bcc_filtrado = bcc_filtrado_full[
                [col for col in colunas_bloqueios_bcc if col in bcc_filtrado_full.columns]
            ].copy()
            
            bcn_filtrado = bcn_filtrado_full[
                    [col for col in colunas_bloqueios_bcn if col in bcn_filtrado_full.columns]
                ].copy()

            tcd_filtrado = tcd_filtrado_full[
                    [col for col in colunas_bloqueios_tcd if col in tcd_filtrado_full.columns]
                ].copy()
            
            #Desenho do buffer
            buffer_casos_gdf = None
            if not casos_filtrados.empty:
                try:
                    casos_projetados = casos_filtrados.to_crs(epsg=31983)
                    buffer_projetado = casos_projetados.geometry.buffer(150)
                    buffer_unido = buffer_projetado.unary_union
                    buffer_casos_gdf = gpd.GeoDataFrame(geometry=[buffer_unido], crs = 31983).to_crs(epsg=4326)
                except Exception as e:
                    st.warning(f"Não foi possível gerar o buffer: {e}")
                
            uvis_texto = ", ".join(map(str, sorted(uvis_tuple)))
            se_texto = ", ".join(map(str, sorted(semanas_tuple)))

            st.markdown("---")
            st.subheader(f"Visualização do Mapa - {len(casos_filtrados)} casos confirmados na(s) UVIS {uvis_texto} na(s) SE {se_texto}")

            if casos_filtrados.empty:
                st.warning("Nenhum caso para o período selecionado.")
            else:
                with st.spinner("Gerando mapa..."):
                    pontos = preparar_pontos_para_cluster(casos_filtrados)
                    mapa_html = criar_mapa_html(
                        pontos, 
                        uvis,
                        crs, 
                        quadras_filtradas, 
                        buffer_gdf=buffer_casos_gdf,
                        bcc_gdf=bcc_filtrado,
                        bcn_gdf=bcn_filtrado,
                        tcd_gdf=tcd_filtrado
                        )
                    # salvar HTML em session_state para reutilizar entre reruns (zoom/scroll)
                    st.session_state["map_html"] = mapa_html
                    st.session_state["map_needs_update"] = False

        #Exibir mapa
        if "map_html" in st.session_state:
           # renderiza o HTML diretamente — isso evita re-criar o folium.Map no backend em cada interação
           components.html(st.session_state["map_html"], height=800, scrolling=True)
        else:
            st.info("Clique em 'Gerar mapa' para criar o mapa.")

except FileNotFoundError:
    st.error("Arquivo não encontrado — verifique os caminhos dos shapefiles.")
except Exception as e:
    st.exception(f"Erro: {e}")
st.markdown("---")    
#-----------------------------#
