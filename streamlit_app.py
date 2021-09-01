import pandas as pd
import streamlit as st
import altair as alt
import base64
import gc

alt.data_transformers.disable_max_rows()

st.set_page_config(page_title="COVID Metro Areas Explorer",layout='centered')

def _max_width_():
    max_width_str = f"max-width: 2000px;"
    st.markdown(
        f"""
    <style>
    .reportview-container .main .block-container{{
        {max_width_str}
        padding-top: 0rem;
    }}
    </style>    
    """,
        unsafe_allow_html=True,
    )

_max_width_()

@st.cache(suppress_st_warning=True, max_entries=10, ttl=3600)
def get_states_shapes():
    print('getstateshapes cache miss')
    return alt.topo_feature('https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/us-10m.json', 'states')

@st.cache(suppress_st_warning=True, max_entries=10, ttl=3600)
def get_source():
    print('getsource cache miss')
    return pd.read_csv('cbsa_timeseries.csv', parse_dates=['report_date'])

@st.cache(suppress_st_warning=True, max_entries=10, ttl=3600)
def make_basemap():
    print('basemap cache miss')
    states_altair = get_states_shapes()
    return alt.Chart(states_altair).mark_geoshape(
            fill=None,
            stroke='gray',
            strokeWidth=0.5,
        ).project('albersUsa')

source = get_source()
states_list = ['All USA']+sorted(source['state'].unique())

# Sidebar stuff
st.sidebar.title('**COVID Metro Areas Data Explorer**')

with st.sidebar.form(key='select_state'):
    selected_states = st.selectbox('Select State to Visualize', states_list)
    submit_button = st.form_submit_button(label='Show State')

st.sidebar.markdown(
    """
    Explore COVID-19 trends in all US metro areas defined as [Core-Based Statistical Areas](https://en.wikipedia.org/wiki/Core-based_statistical_area) (CBSAs). 
    
    Metric shown:
    - Confirmed COVID-19 new hospital admissions (7-day totals and 7-day totals per 100k population) per week in 2021
        
    Data source: [COVID-19 Community Profile Reports](https://healthdata.gov/Health/COVID-19-Community-Profile-Report/gqxm-d9w9)

    Data wrangling and visualizations by Dave Luo.
    """
)
if selected_states != 'All USA': source = source[source['state']==selected_states]
# default cbsas to display
cbsa_init = [{'cbsa':c} for c in source[(source['report_date']==source['report_date'].max())\
                                        ].sort_values('admissions_covid_confirmed_last_7_days', ascending=False)['cbsa'].values[:10]]

@st.cache(max_entries=10, ttl=3600)
def get_counties_shapes():
    return alt.topo_feature('https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/us-10m.json', 'counties')

@st.cache(suppress_st_warning=True, max_entries=10, ttl=3600)
def get_cbsa_shapes():
    st.write('getcbsa cache miss')
    return alt.topo_feature('https://raw.githubusercontent.com/daveluo/covid-metro-explorer/main/cbsa_shapes.json', 'cbsa_shapes')

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

# selections
if selected_states != 'All USA': empty_default = 'all'
else: empty_default = 'none'

select_cbsa = alt.selection_multi(name='cbsa', empty=empty_default, nearest=True, fields=['cbsa'], init=cbsa_init)
slider = alt.binding_range(min=0, max=source['timeslider'].max(), step=1, name=' ')
select_date = alt.selection_single(name="timeslide", fields=['timeslider'], bind=slider, init={'timeslider':source['timeslider'].max()})

# line plots
legend_base = alt.Chart(source).encode(
    x=alt.X('report_date:T', axis=alt.Axis(orient='bottom',title='',labelAngle=0,), sort=alt.SortOrder('ascending'),),
    color= alt.Color('cbsa:O', scale=alt.Scale(scheme='category10'), legend=alt.Legend(title='CBSA Name', labelLimit=1000)),  
    opacity=alt.value(0.7))

legend_line = legend_base.mark_line(strokeWidth=1.5).encode(
    y=alt.Y('admits_100k', title=None),
    tooltip=['cbsa','report_date','hosp_timerange','admits_100k','total_population_2019'],
).transform_filter(select_cbsa)

legend_points = legend_line.mark_point(shape='circle', filled=True, size=30
).properties(title='Weekly New Admissions per 100k').transform_filter(select_date).add_selection(select_cbsa)

legend_abs_line = legend_base.mark_line(strokeWidth=1.5).encode(
    y=alt.Y('admissions_covid_confirmed_last_7_days', title=None),
    tooltip=['cbsa','report_date','hosp_timerange','admissions_covid_confirmed_last_7_days','total_population_2019'],
).transform_filter(select_cbsa)

legend_abs_points = legend_abs_line.mark_point(shape='circle', filled=True, size=30
).properties(title='Weekly New Admissions').transform_filter(select_date).add_selection(select_cbsa)

# map plot
map_background = make_basemap()

map_facility_base = alt.Chart(source).mark_point(filled=True).encode(
    longitude='lon',
    latitude='lat',
    color = alt.Color('admits_100k:Q', 
                    legend=alt.Legend(orient='none', legendX=380, legendY=570, direction='horizontal', titleLimit=500, format='.0f'),
                    title='Weekly Admissions per 100k',
                    scale=alt.Scale(scheme='redyellowblue', domain=[0,75], type='quantile', reverse=True, clamp=True),
                    ), 
    size= alt.Size('admissions_covid_confirmed_last_7_days:Q', 
                    title=['Weekly Admissions'],
                    legend=alt.Legend(orient='none', legendX=620, legendY=570, direction='horizontal', titleLimit=500), scale=alt.Scale(domain=[0,2500], range=[10,500])
                    ),
    stroke=alt.condition(select_cbsa, alt.value('black'), alt.value('#111111')),
    strokeWidth=alt.condition(select_cbsa, alt.value(1.5), alt.value(0.5)),
    tooltip=['cbsa','report_date','hosp_timerange','total_population_2019','admissions_covid_confirmed_last_7_days','admits_100k',],
).transform_filter(alt.datum.state!='PR').add_selection(select_cbsa).add_selection(select_date).transform_filter(select_date)

date_display = alt.Chart(source).mark_text(dy=300, dx=-300, size=24, stroke='white', strokeWidth=0.3).encode(
    text='hosp_timerange:N'
).transform_filter(select_date).transform_filter(alt.datum.cbsa==cbsa_init[0]['cbsa'])

map_text = alt.Chart(source).mark_text(dy=-12, dx=0, size=12, opacity=1, color='#000', stroke='#fff', strokeWidth=0.).encode(
    longitude='lon',
    latitude='lat',
    text='cbsa_short'
).transform_filter(select_cbsa).transform_filter(select_date).transform_filter(alt.datum.state!='PR')

@st.cache(allow_output_mutation=True, max_entries=10, ttl=3600)
def make_vizconcat(selected_states):
    print('vizconcat cache miss')
    if selected_states != 'All USA': 
        cbsa_shapes = get_cbsa_shapes()
        map_cbsa = alt.Chart(cbsa_shapes).mark_geoshape(
            fill='#e5e5e5',
            stroke='white',
            strokeWidth=2,
            strokeOpacity=1,
        ).project('albersUsa').transform_calculate(state='datum.properties.state').transform_filter(alt.datum.state==selected_states)
            
        viz_concat = (map_cbsa+map_background.transform_filter(alt.datum.id == int(state_codes[selected_states]))      
                            +map_facility_base.transform_filter(alt.datum.state==selected_states)
                            +date_display.transform_filter(alt.datum.state==selected_states)
                            +map_text.transform_filter(alt.datum.state==selected_states)
                            )
    else: 
        viz_concat = (map_background+map_facility_base+date_display+map_text)
    
    return viz_concat

viz_concat = make_vizconcat(selected_states)

maptime_viz = alt.vconcat(viz_concat.properties(
                        title=['',f'{selected_states} Metro Areas - New COVID-19 Hospital Admissions per Week'],
                        height=550, width=1000),
                        (legend_line+legend_points).interactive().properties(width=250, height=250,)|
                        (legend_abs_line+legend_abs_points).interactive().properties(width=250, height=250,)
                        ).properties( 
                            center=True,
                        ).configure_axis(
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
            left: 30px;
            top: 630px;
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
st.header('Explore Map and Time Trends')

st.altair_chart(maptime_viz, use_container_width=False)

st.info("""
    Use slider to update map visualization through time. Click points on map to select metros for timeseries plots (shift-click to select multiple, double-click to clear selection). Click "..." circle icon on top-right to save visualization as SVG or PNG. Explore/export data as tables and see sources in bottom section.
""")
with st.expander("See more visualization details"):
    st.markdown(
    """
    Data updated weekly with reporting date range displayed below map.

    Bubble size is scaled to absolute 7-day-totals. Bubble color is scaled to 7-day-totals per capita (usually per 100k population).
    
    National-level map view shows state borders as dark lines. State-level map show CBSAs as light-grey-filled shapes.

    Puerto Rico (PR) data not shown on map but does appear in time line plots and table view.

    Bubble locations on map represent an internal lat/lon coordinate for each CBSA shape as designated by US Census data [here](https://catalog.data.gov/dataset/tiger-line-shapefile-2019-nation-u-s-current-metropolitan-statistical-area-micropolitan-statist) and are NOT precise locations of metro areas. CBSA shapes can cross state borders and bubble centers may appear over water bodies (sorry WI and MI).

    Community Profile Report data represents weekly snapshots in time and are not backfilled or revised. Data anomalies and reporting errors may be seen here without correction as a result.
    """
    )

cbsas = source['cbsa'].unique()

st.header(f'See Metro Area Data for {selected_states} as Table')
with st.form(key='my_form'):
    if selected_states != 'All USA':
        selected_cbsas = st.multiselect('Select Metro Area(s)', cbsas, default=cbsas)
    else:
        selected_cbsas = st.multiselect('Select Metro Area(s)', cbsas)
    submit_button = st.form_submit_button(label='Create Table')

display_df = source[source['cbsa'].isin(selected_cbsas)]\
    [['cbsa','report_date','hosp_timerange', 'admissions_covid_confirmed_last_7_days','admits_100k','total_population_2019', 'lat','lon']]
display_df['report_date'] = display_df['report_date'].apply(lambda x: x.strftime('%Y-%m-%d'))
display_df.sort_values(['cbsa','report_date'], ascending=[True,False], inplace=True)
st.dataframe(display_df)

# thanks https://discuss.streamlit.io/t/export-and-download-dataframe-to-csv-file/9926/3
def get_table_download_link_csv(df):
    csv = df.to_csv().encode()
    b64 = base64.b64encode(csv).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="covid_metroareas_export.csv" target="_blank">Export displayed table as CSV</a>'
    return href

st.markdown(get_table_download_link_csv(display_df), unsafe_allow_html=True)

# thanks https://discuss.streamlit.io/t/display-urls-in-dataframe-column-as-a-clickable-hyperlink/743/5
def make_clickable(link):
    return f'<a target="_blank" href="{link}">{link}</a>'

st.header('Data Source Description')
st.markdown("""
**From COVID-19 Community Profile Report data hosting page on [HealthData.gov](https://www.healthdata.gov/Health/COVID-19-Community-Profile-Report/gqxm-d9w9):**

>The Community Profile Report (CPR) is generated by the Data Strategy and Execution Workgroup in the Joint Coordination Cell, under the White House COVID-19 Team. It is managed by an interagency team with representatives from multiple agencies and offices (including the United States Department of Health and Human Services, the Centers for Disease Control and Prevention, the Assistant Secretary for Preparedness and Response, and the Indian Health Service). The CPR provides easily interpretable information on key indicators for all regions, states, core-based statistical areas (CBSAs), and counties across the United States. It is a snapshot in time that:
- Focuses on recent COVID-19 outcomes in the last seven days and changes relative to the week prior
- Provides additional contextual information at the county, CBSA, state and regional levels
- Supports rapid visual interpretation of results with color thresholds*
Data in this report may differ from data on state and local websites. This may be due to differences in how data were reported (e.g., date specimen obtained, or date reported for cases) or how the metrics are calculated. Historical data may be updated over time due to delayed reporting. Data presented here use standard metrics across all geographic levels in the United States. It facilitates the understanding of COVID-19 pandemic trends across the United States by using standardized data. The footnotes describe each data source and the methods used for calculating the metrics. For additional data for any particular locality, visit the relevant health department website. Additional data and features are forthcoming. 

>\*Color thresholds for each category are defined on the color thresholds tab

>Effective April 30, 2021, the Community Profile Report will be distributed on Monday through Friday. There will be no impact to the data represented in these reports due to this change  

>Effective June 22, 2021, the Community Profile Report will only be updated twice a week, on Tuesdays and Fridays.
"""
)
with st.expander('Access Community Profile Report source data files'):
    st.markdown('Direct link to each data file listed below:')
    source_df = pd.read_csv('cpr_sources.csv')[['report_date','source_url']]
    source_df['source_url'] = source_df['source_url'].apply(make_clickable)
    source_df.rename({'report_date':'Report Date',
                    'source_url':'Excel file direct download URL'
                        }, axis=1, inplace=True)
    source_df = source_df.to_html(escape=False, index=False)
    st.write(source_df, unsafe_allow_html=True)

gc.collect()