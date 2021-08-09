import pandas as pd
import geopandas as gpd
import streamlit as st
import altair as alt
import base64
alt.data_transformers.disable_max_rows()

@st.cache
def get_data(): return pd.read_csv('cbsa_timeseries.csv', parse_dates=['report_date'])

@st.cache
def get_states_shapes():
    return alt.topo_feature('https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/us-10m.json', 'states')

@st.cache
def make_source_df(cbsa_merged):
    source = cbsa_merged[['cbsa','cbsa_short','report_date',
        'admissions_covid_confirmed_last_7_days','admits_100k',
        'state','lat','lon', 'total_population_2019']]

    timeslider_dict = {k:i for i,k in enumerate(sorted(source['report_date'].astype('str').unique()))}
    source['timeslider'] = source['report_date'].astype('str').apply(lambda x: int(timeslider_dict[x]))
    source['cbsa_short'] = source['cbsa'].apply(lambda x: x.split(',')[0].rstrip().lstrip())

    bluffton_lat, bluffton_lon = 40.738638307693904, -85.17187672851077
    source.loc[source['cbsa']=='Bluffton, IN', 'lat'] = bluffton_lat
    source.loc[source['cbsa']=='Bluffton, IN', 'lon'] = bluffton_lon
    return source

cbsa_merged = get_data()
states_altair = get_states_shapes()
source = make_source_df(cbsa_merged)

states_list = ['All USA']+sorted(source['state'].unique())

# Sidebar stuff

st.sidebar.markdown(
    """
    **COVID US Metro Areas Explorer**
      
    Explore COVID-19 trends in all US metro areas as defined by [Core-Based Statistical Areas](https://en.wikipedia.org/wiki/Core-based_statistical_area) (CBSAs). 
    
    Use slider to visualize map through time. Click points on map to select metros for time line plots (shift-click to select multipe). Explore and export data as table in bottom section.
    
    Data shown:
    - confirmed adult COVID-19 new hospital admissions (7-day totals) per week in 2021

    Data sources: CDC and HHS  
    Created by Dave Luo
    """
)

with st.sidebar.form(key='select_state'):
    selected_states = st.selectbox('Select State', states_list)
    submit_button = st.form_submit_button(label='Show State')

with st.sidebar.expander("See more visualization details"):
    st.markdown(
    """
    Data updated weekly with last reporting date displayed below map.

    Bubble size represents absolute totals. Bubble color represents per capita (usually metric per 100k population). 
    
    National-level map view shows state outlines. State-level map show CBSA outlines.

    Puerto Rico (PR) data not shown on map but does appear in time line plots and table view.

    Point locations on map represent an internal lat/lon coordinate for each CBSA shape as designated by US Census data [here](https://catalog.data.gov/dataset/tiger-line-shapefile-2019-nation-u-s-current-metropolitan-statistical-area-micropolitan-statist) and is NOT the precise location of any one metro area. Locations may appear across state borders and sometimes over water bodies (sorry WI and MI).
    """
    )

# default cbsas to display
if selected_states != 'All USA': 
    source = source[source['state']==selected_states]
    cbsa_init = [{'cbsa':c} for c in source[(source['report_date']==source['report_date'].max())\
                                            ].sort_values('admissions_covid_confirmed_last_7_days', ascending=False)['cbsa'].values[:8]]
else: 
    cbsa_init = [{'cbsa':c} for c in source[(source['report_date']==source['report_date'].max())\
                                            &(source['admissions_covid_confirmed_last_7_days']>1000)\
                                            ].sort_values('admissions_covid_confirmed_last_7_days', ascending=False)['cbsa'].values[:4]]

# selections
select_cbsa = alt.selection_multi(name='cbsa', empty='none', nearest=True, fields=['cbsa'], init=cbsa_init)
slider = alt.binding_range(min=0, max=source['timeslider'].max(), step=1, name='Select Week:')
select_date = alt.selection_single(name="timeslide", fields=['timeslider'], bind=slider, init={'timeslider':source['timeslider'].max()})

# line plots
legend_base = alt.Chart(source).encode(
    x=alt.X('report_date:T', axis=alt.Axis(orient='bottom',title='',labelAngle=0,), sort=alt.SortOrder('ascending'),),
    color= alt.condition(select_date, alt.Color('cbsa:O', scale=alt.Scale(scheme='dark2')), alt.value('lightgray')),  
)

legend_points = legend_base.mark_point(shape='circle', filled=True, size=50, opacity=0.8).encode(
    y=alt.Y('admits_100k', title=None),
    opacity = alt.condition(select_date, alt.value(0.8), alt.value(0.)),
).add_selection(select_date
).transform_filter(select_cbsa)

legend_line = legend_base.mark_line().transform_filter(select_cbsa).encode(
    y=alt.Y('admits_100k', title=None),
    color= alt.Color('cbsa:O', scale=alt.Scale(scheme='category20'), legend=alt.Legend(title='CBSA Name', labelLimit=1000)),  
).transform_filter(select_cbsa).properties(title='Weekly New Admissions per 100k')

legend_abs_points = legend_base.mark_point(shape='circle', filled=True, size=50, opacity=0.8).encode(
    y=alt.Y('admissions_covid_confirmed_last_7_days', title=None),
    opacity = alt.condition(select_date, alt.value(0.8), alt.value(0.)),
).add_selection(select_date
).transform_filter(select_cbsa)

legend_abs_line = legend_base.mark_line().transform_filter(select_cbsa).encode(
    y=alt.Y('admissions_covid_confirmed_last_7_days', title=None),
    color= alt.Color('cbsa:O', scale=alt.Scale(scheme='category20'), legend=None)#alt.Legend(title='CBSA Name', labelLimit=1000)),  
).transform_filter(select_cbsa).properties(title='Weekly New Admissions')


# @st.cache
def get_counties_shapes():
    return alt.topo_feature('https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/us-10m.json', 'counties')

# @st.cache
def get_cbsa_shapes():
    return alt.topo_feature('https://gist.githubusercontent.com/daveluo/ab3bbb49b563393acf5a910ba481ea4d/raw/26ec4896920891565c856acc05593490b8acf1d1/cbsa_shapes.json', 'cbsa_shapes')

state_codes = {
    'WA': '53', 'DE': '10', 'DC': '11', 'WI': '55', 'WV': '54', 'HI': '15',
    'FL': '12', 'WY': '56', 'PR': '72', 'NJ': '34', 'NM': '35', 'TX': '48',
    'LA': '22', 'NC': '37', 'ND': '38', 'NE': '31', 'TN': '47', 'NY': '36',
    'PA': '42', 'AK': '02', 'NV': '32', 'NH': '33', 'VA': '51', 'CO': '08',
    'CA': '06', 'AL': '01', 'AR': '05', 'VT': '50', 'IL': '17', 'GA': '13',
    'IN': '18', 'IA': '19', 'MA': '25', 'AZ': '04', 'ID': '16', 'CT': '09',
    'ME': '23', 'MD': '24', 'OK': '40', 'OH': '39', 'UT': '49', 'MO': '29',
    'MN': '27', 'MI': '26', 'RI': '44', 'KS': '20', 'MT': '30', 'MS': '28',
    'SC': '45', 'KY': '21', 'OR': '41', 'SD': '46', 'VI': '78', 'GU': '66',
    'MP': '69', 'AS': '60',
}

# map plot
# states = get_states_shapes()
map_background = alt.Chart(states_altair).mark_geoshape(
    fill=None,
    stroke='gray',
    strokeWidth=0.5,
).project('albersUsa')

map_facility_base = alt.Chart(source).mark_point(filled=True).encode(
    longitude='lon',
    latitude='lat',
    color = alt.Color('admits_100k:Q', 
                    legend=alt.Legend(orient='none', legendX=420, legendY=470, direction='horizontal', titleLimit=500, format='.0f'),
                    title='Weekly Admissions per 100k',
                    scale=alt.Scale(scheme='redyellowblue', domain=[0,50], type='quantile', reverse=True, clamp=True),
                    ), 
    size= alt.Size('admissions_covid_confirmed_last_7_days:Q', 
                    title=['Weekly','Admissions'],
                    legend=alt.Legend(orient='none', legendX=700, legendY=350, direction='vertical', titleLimit=500), scale=alt.Scale(domain=[0,2000], range=[10,500])
                    ),
    stroke=alt.condition(select_cbsa, alt.value('black'), alt.value('#111111')),
    strokeWidth=alt.condition(select_cbsa, alt.value(1.5), alt.value(0.5)),
    tooltip=['cbsa','report_date','timeslider','total_population_2019','admissions_covid_confirmed_last_7_days','admits_100k',],
).transform_filter(alt.datum.state!='PR').add_selection(select_cbsa).add_selection(select_date).transform_filter(select_date)

date_display = alt.Chart(source).mark_text(dy=250, dx=-100, size=18).encode(
    text='report_date:T'
).transform_filter(select_date).transform_filter(alt.datum.cbsa==cbsa_init[0]['cbsa'])

map_text = alt.Chart(source).mark_text(dy=-10, dx=0, size=12, opacity=0.8).encode(
    longitude='lon',
    latitude='lat',
    text='cbsa_short'
).transform_filter(select_cbsa).transform_filter(select_date).transform_filter(alt.datum.state!='PR')

if selected_states != 'All USA': 
    cbsa_shapes = get_cbsa_shapes()
    map_cbsa = alt.Chart(cbsa_shapes).mark_geoshape(
        fill=None,
        stroke='lightgrey',
        strokeWidth=2,
        strokeOpacity=0.5,
    ).project('albersUsa').transform_calculate(state='datum.properties.state').transform_filter(alt.datum.state==selected_states)
        
    viz_concat = (map_background.transform_filter(alt.datum.id == int(state_codes[selected_states]))
                        +map_cbsa
                        +map_facility_base.transform_filter(alt.datum.state==selected_states)
                        +date_display.transform_filter(alt.datum.state==selected_states)
                        +map_text.transform_filter(alt.datum.state==selected_states)
                        )
else: 
    viz_concat = (map_background+map_facility_base+date_display+map_text)

maptime_viz = alt.vconcat(viz_concat.properties(width=700, height=450), 
                          (legend_line+legend_points).interactive(bind_x=False).properties(width=500, height=200,),
                          (legend_abs_line+legend_abs_points).interactive(bind_x=False).properties(width=500, height=200,)
                        ).properties( 
                            title=[f'{selected_states} Metro Areas - New COVID-19 Hospital Admission Trends by Week'],
                            center=False,
                        ).configure(padding={ 'top' : 0 }).configure_axis(
                            labelFontSize=14,
                            titleFontSize=14
                        ).configure_header(
                            titleFontSize=14,
                            labelFontSize=14
                        ).configure_title(
                            fontSize=16
                        ).configure_legend(
                            titleFontSize=12,
                            labelFontSize=12
                        ).configure_view(strokeWidth=0)

st.markdown(f"""
    <style>

        form.vega-bindings {{
            position: absolute;
            left: 0px;
            top: 510px;
            font-family: 'arial';
        }}
        form.vega-bindings input {{
            width: 300px;
        }}
        form.vega-bindings label span {{
            color: #ffffff;
            opacity: 0;
        }}

    </style>
    """,
    unsafe_allow_html=True,
)
st.header('Map and Time Trends')
st.altair_chart(maptime_viz)

cbsas = source['cbsa'].unique()

st.header(f'Explore Metro Area Data for {selected_states} as a Table')
with st.form(key='my_form'):
    if selected_states != 'All USA':
        selected_cbsas = st.multiselect('Select Metro Area(s)', cbsas, default=cbsas)
    else:
        selected_cbsas = st.multiselect('Select Metro Area(s)', cbsas)
    submit_button = st.form_submit_button(label='Create Table')

display_df = source[source['cbsa'].isin(selected_cbsas)]\
    [['cbsa','report_date','admissions_covid_confirmed_last_7_days','admits_100k','total_population_2019', 'lat','lon']]
display_df['report_date'] = display_df['report_date'].apply(lambda x: x.strftime('%Y-%m-%d'))
display_df.sort_values(['cbsa','report_date'], ascending=[True,False], inplace=True)
st.dataframe(display_df)

# thanks https://discuss.streamlit.io/t/export-and-download-dataframe-to-csv-file/9926/3
def get_table_download_link_csv(df):
    csv = df.to_csv().encode()
    b64 = base64.b64encode(csv).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="covid_metroareas_export.csv" target="_blank">Download displayed table as CSV</a>'
    return href

st.markdown(get_table_download_link_csv(display_df), unsafe_allow_html=True)