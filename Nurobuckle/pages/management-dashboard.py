import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import os
import threading
import logging
import time
import sys
from collections import deque
import folium
from folium.plugins import MarkerCluster

# Add parent directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Add python directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'EEG'))
from cortex import Cortex

# Import functions from app.py
from Nurobuckle.app import send_fatigue_alerts, find_nearby_restaurants, get_current_location, create_map, calculate_distance
import asyncio

# Silence unwanted logs
logging.getLogger().setLevel(logging.ERROR)

class MetAttentionLogger:
    def __init__(self, client_id, client_secret, **kwargs):
        self.cortex = Cortex(client_id, client_secret, debug_mode=False, **kwargs)
        self.cortex.bind(create_session_done=self.on_session_ready)
        self.cortex.bind(new_met_data=self.on_new_met_data)
        self.last_print_time = 0
        self.print_interval = 1  # Update every second for smooth visualization
        self.attention_history = deque(maxlen=480)  # Store 8 hours of data (480 minutes)
        self.current_attention = 0
        self.alert_sent = False  # Track if alert has been sent
        
    def start(self, duration=None, headset_id=''):
        self.streams = ['met']
        if headset_id:
            self.cortex.set_wanted_headset(headset_id)
        self.cortex.open()
        if duration:
            threading.Timer(duration, self.stop).start()

    def stop(self):
        self.cortex.unsub_request(self.streams)
        self.cortex.close()

    def on_session_ready(self, *args, **kwargs):
        print("Connected to Cortex. Subscribing to 'met' stream...")
        self.cortex.sub_request(self.streams)

    async def check_and_send_alerts(self):
        print(f"Checking attention level: {self.current_attention}")
        if self.current_attention < 8.0 and not self.alert_sent:
            print("Attention below threshold! Sending alerts...")
            try:
                # Send fatigue alerts and get gas station info
                result = await send_fatigue_alerts()
                print(f"Alert result: {result}")
                
                if "error" not in result:
                    # Get current location for map update
                    location_data = await get_current_location()
                    print(f"Location data: {location_data}")
                    
                    if "error" not in location_data:
                        gas_station = result["gas_station"]
                        
                        # Update map with gas station
                        st.session_state.map = create_map(
                            location_data["latitude"],
                            location_data["longitude"],
                            location_data["city"],
                            gas_station
                        )
                        
                        # Store gas station info
                        distance = calculate_distance(
                            location_data["latitude"],
                            location_data["longitude"],
                            gas_station["location"]["lat"],
                            gas_station["location"]["lng"]
                        )
                        
                        st.session_state.gas_station_info = {
                            "name": gas_station["name"],
                            "address": gas_station["address"],
                            "distance": distance
                        }
                        
                        # Find nearby restaurants
                        restaurants = await find_nearby_restaurants()
                        if restaurants:
                            st.session_state.restaurants = restaurants
                            print(f"Found {len(restaurants)} restaurants")
                        
                        self.alert_sent = True
                        print("Alert process completed successfully")
                        st.rerun()
            except Exception as e:
                print(f"Error in alert process: {str(e)}")
                import traceback
                print(traceback.format_exc())

    def on_new_met_data(self, *args, **kwargs):
        current_time = time.time()
        if current_time - self.last_print_time < self.print_interval:
            return

        data = kwargs.get('data', {})
        met = data.get('met', [])
        timestamp = datetime.now()

        # foc.isActive = index 11, foc = index 12
        if len(met) > 12 and met[11] and met[12] is not None:
            raw_attention = met[12]
            if not (0 <= raw_attention <= 1):
                print(f"⚠️ Unexpected attention value: {raw_attention}")
            attention = round(min(max(raw_attention, 0), 1) * 10, 2)
            print(f"New attention value: {attention}")  # Debug log
            self.current_attention = attention
            self.attention_history.append((timestamp, attention))
            self.last_print_time = current_time
            
            # Create a new event loop for the async call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.check_and_send_alerts())
            finally:
                loop.close()

# Initialize session state
if 'attention_logger' not in st.session_state:
    st.session_state.attention_logger = MetAttentionLogger(
        client_id='fuzggT9x1AydQhgGJ2adj6vDC4KM5Hm3tEFY5hJO',
        client_secret='bQgM4tjsSmxSF0N4qmKiMA46HkogPQnvn92Tkvl8iXYfoUWuC49n9NFgbd3MXXqCZ35MqEmmGqrkEecmtRmvmmGmweZyRD7cETdbDQegW033hxK8vGsbwQImhLSlXlSj',
        license='0657f307-6ab8-4f14-9c93-be103633fd58'
    )
    st.session_state.attention_logger.start()

# Initialize other session states if not exists
if 'map' not in st.session_state:
    st.session_state.map = None
if 'restaurants' not in st.session_state:
    st.session_state.restaurants = None
if 'gas_station_info' not in st.session_state:
    st.session_state.gas_station_info = None

# Page config
st.set_page_config(
    page_title="Management Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title
st.title("Management Dashboard")

# Create attention gauge
st.subheader("Current Attention Level")

# Get current attention from logger
current_attention = st.session_state.attention_logger.current_attention

# Create attention gauge
fig_attention = go.Figure(go.Indicator(
    mode="gauge+number",
    value=current_attention,
    title={'text': "Current Attention Level (0-10)"},
    gauge={
        'axis': {'range': [0, 10]},
        'bar': {'color': "darkblue"},
        'steps': [
            {'range': [0, 5], 'color': "red"},
            {'range': [5, 7.5], 'color': "yellow"},
            {'range': [7.5, 10], 'color': "green"}
        ],
        'threshold': {
            'line': {'color': "black", 'width': 4},
            'thickness': 0.75,
            'value': 7.5
        }
    }
))
fig_attention.update_layout(height=300)
st.plotly_chart(fig_attention, use_container_width=True)

# Display alert status and map
if st.session_state.attention_logger.alert_sent:
    st.warning("⚠️ Low attention detected! Alerts sent and route updated.")
    
    # Display gas station information if available
    if st.session_state.gas_station_info and st.session_state.gas_station_info.get('name'):
        st.subheader("🛑 Recommended Rest Stop")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"<div style='font-size: 14px;'><strong>Gas Station:</strong><br>{st.session_state.gas_station_info['name']}</div>",
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                f"<div style='font-size: 14px;'><strong>Distance:</strong><br>{st.session_state.gas_station_info['distance']} mi</div>",
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                f"<div style='font-size: 14px;'><strong>Address:</strong><br>{st.session_state.gas_station_info['address']}</div>",
                unsafe_allow_html=True
            )
    
    # Display the map if available
    if st.session_state.map:
        st.subheader("📍 Route Map")
        folium_static(st.session_state.map, width=700, height=400)

    # Display restaurants if available
    if st.session_state.restaurants:
        st.subheader("🍽️ Nearby Restaurants")
        for place in st.session_state.restaurants:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**{place['name']}**")
                st.write(f"📍 {place['address']}")
            with col2:
                if place.get('rating'):
                    st.write(f"⭐ Rating: {place['rating']}")
            st.write("---")

# Timeline
st.subheader("Live Attention Timeline")
if len(st.session_state.attention_logger.attention_history) > 0:
    history_df = pd.DataFrame(
        st.session_state.attention_logger.attention_history,
        columns=['timestamp', 'attention']
    )
    
    fig_timeline = go.Figure()
    fig_timeline.add_trace(go.Scatter(
        x=history_df['timestamp'],
        y=history_df['attention'],
        name='Attention Level',
        line=dict(color='blue')
    ))
    
    st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.info("Waiting for attention data...")

# Auto-refresh the dashboard
st.empty()
time.sleep(1)
st.rerun()