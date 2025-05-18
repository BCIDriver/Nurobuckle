import streamlit as st
import asyncio
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, List, Tuple
import httpx
from twilio.rest import Client
from dotenv import load_dotenv
import os
import folium
from streamlit_folium import folium_static
from folium.plugins import AntPath
import polyline
from math import radians, sin, cos, sqrt, atan2, degrees

# Load environment variables
load_dotenv()

# Initialize the MCP server
mcp = FastMCP("NearbySearch")

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# IPInfo token
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", "YOUR_IPINFO_TOKEN")  # Get free token from ipinfo.io

async def get_current_location() -> Dict[str, Any]:
    """Get current location based on IP using ipinfo.io"""
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": f"Bearer {IPINFO_TOKEN}"} if IPINFO_TOKEN != "YOUR_IPINFO_TOKEN" else {}
            response = await client.get("https://ipinfo.io/json", headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Parse location from loc field (format: "latitude,longitude")
            if "loc" in data:
                lat, lon = map(float, data["loc"].split(","))
            else:
                return {"error": "Missing location data in response"}
                
            return {
                "latitude": lat,
                "longitude": lon,
                "city": data.get("city", "Unknown"),
                "region": data.get("region", "Unknown"),
                "country": data.get("country", "Unknown")
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {str(e)}"}
        except ValueError as e:
            return {"error": f"Invalid data format: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

async def get_driving_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> List[Tuple[float, float]]:
    """Get driving directions using Google Directions API"""
    api_key = "AIzaSyDd1w5vqAmrcTe4C7kZsb5oZCjt2-3wXXw"  # Using the same key as in search_nearby
    async with httpx.AsyncClient() as client:
        try:
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                "origin": f"{origin_lat},{origin_lon}",
                "destination": f"{dest_lat},{dest_lon}",
                "mode": "driving",
                "key": api_key
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data["status"] != "OK":
                return []
            
            # Extract the polyline points from the first route
            route = data["routes"][0]
            points = polyline.decode(route["overview_polyline"]["points"])
            return points
        except Exception as e:
            st.error(f"Error getting driving directions: {str(e)}")
            return []

async def find_nearest_gas_station(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    """Find a gas station along the route to YC using Google Places API"""
    api_key = "AIzaSyDd1w5vqAmrcTe4C7kZsb5oZCjt2-3wXXw"
    # YC Palo Alto coordinates
    yc_lat, yc_lon = 37.4443, -122.1607
    
    async with httpx.AsyncClient() as client:
        try:
            # First get the route to YC
            route_url = "https://maps.googleapis.com/maps/api/directions/json"
            route_params = {
                "origin": f"{latitude},{longitude}",
                "destination": f"{yc_lat},{yc_lon}",
                "mode": "driving",
                "key": api_key
            }
            route_response = await client.get(route_url, params=route_params)
            route_response.raise_for_status()
            route_data = route_response.json()
            
            if route_data["status"] != "OK":
                return None
            
            # Get the route points
            route = route_data["routes"][0]
            points = polyline.decode(route["overview_polyline"]["points"])
            
            # Find a point roughly halfway along the route
            midpoint_idx = len(points) // 2
            midpoint = points[midpoint_idx]
            
            # Search for gas stations near the midpoint
            places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            places_params = {
                "location": f"{midpoint[0]},{midpoint[1]}",
                "radius": 2000,  # 2km radius around midpoint
                "type": "gas_station",
                "key": api_key
            }
            places_response = await client.get(places_url, params=places_params)
            places_response.raise_for_status()
            places_data = places_response.json()
            
            if places_data["status"] != "OK" or not places_data.get("results"):
                return None
            
            # Get the gas station with the highest rating
            station = max(places_data["results"], key=lambda x: x.get("rating", 0))
            return {
                "name": station["name"],
                "location": station["geometry"]["location"],
                "address": station.get("vicinity", "Unknown address")
            }
        except Exception as e:
            st.error(f"Error finding gas station: {str(e)}")
            return None

async def get_driving_route_with_waypoint(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, waypoint_lat: float, waypoint_lon: float) -> List[Tuple[float, float]]:
    """Get driving directions with a waypoint using Google Directions API"""
    api_key = "AIzaSyDd1w5vqAmrcTe4C7kZsb5oZCjt2-3wXXw"
    async with httpx.AsyncClient() as client:
        try:
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                "origin": f"{origin_lat},{origin_lon}",
                "destination": f"{dest_lat},{dest_lon}",
                "waypoints": f"via:{waypoint_lat},{waypoint_lon}",
                "mode": "driving",
                "key": api_key
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data["status"] != "OK":
                return []
            
            # Extract the polyline points from the first route
            route = data["routes"][0]
            points = polyline.decode(route["overview_polyline"]["points"])
            return points
        except Exception as e:
            st.error(f"Error getting driving directions: {str(e)}")
            return []

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles using Haversine formula"""
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c

    return round(distance, 1)

def create_map(latitude: float, longitude: float, city: str, waypoint: Optional[Dict[str, Any]] = None) -> folium.Map:
    """Create a map centered on the current location with driving route to YC"""
    # YC Palo Alto coordinates
    yc_lat, yc_lon = 37.4443, -122.1607
    
    # Google Maps-like style
    map_style = {
        'color': '#4285F4',  # Google Maps blue
        'weight': 4,
        'opacity': 0.8
    }

    # Create map centered on current location
    m = folium.Map(location=[latitude, longitude], zoom_start=10)
    
    # Add marker for current location
    folium.Marker(
        [latitude, longitude],
        popup=f"Current Location: {city}",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    
    # Add marker for YC
    folium.Marker(
        [yc_lat, yc_lon],
        popup="Y Combinator",
        icon=folium.Icon(color='green', icon='info-sign')
    ).add_to(m)
    
    # If waypoint is provided, add it to the map
    if waypoint:
        waypoint_lat = waypoint["location"]["lat"]
        waypoint_lon = waypoint["location"]["lng"]
        
        # Add marker for waypoint
        folium.Marker(
            [waypoint_lat, waypoint_lon],
            popup=f"{waypoint['name']}<br>{waypoint['address']}",
            icon=folium.Icon(color='orange', icon='info-sign')
        ).add_to(m)
        
        # Get route with waypoint
        route_points = asyncio.run(get_driving_route_with_waypoint(
            latitude, longitude,
            yc_lat, yc_lon,
            waypoint_lat, waypoint_lon
        ))
    else:
        # Get direct route to YC
        route_points = asyncio.run(get_driving_route(latitude, longitude, yc_lat, yc_lon))
    
    # Add route to map if available
    if route_points:
        AntPath(
            locations=route_points,
            popup='Route to YC',
            **map_style
        ).add_to(m)
    
    return m

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial bearing between two points"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlon = lon2 - lon1
    y = sin(dlon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    initial_bearing = atan2(y, x)
    
    # Convert to degrees
    initial_bearing = degrees(initial_bearing)
    bearing = (initial_bearing + 360) % 360
    
    return bearing

@mcp.tool()
async def search_nearby(
    keyword: str,
    radius: int = 1500,
    type: Optional[str] = None
) -> Dict[str, Any]:
    """Search for nearby places using Google Places API"""
    api_key = "AIzaSyDd1w5vqAmrcTe4C7kZsb5oZCjt2-3wXXw"
    
    try:
        # First get current location
        location = await get_current_location()
        if "error" in location:
            return {"error": f"Failed to get location: {location['error']}"}
        
        latitude = location["latitude"]
        longitude = location["longitude"]
        
        # Search for nearby places
        async with httpx.AsyncClient() as client:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{latitude},{longitude}",
                "radius": radius,
                "keyword": keyword,
                "key": api_key
            }
            if type:
                params["type"] = type
                
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data["status"] != "OK":
                return {"error": f"Places API error: {data['status']}"}
            
            # Process and return results
            places = []
            for place in data["results"][:5]:  # Limit to top 5 results
                places.append({
                    "name": place["name"],
                    "address": place.get("vicinity", "Unknown address"),
                    "rating": place.get("rating", "No rating"),
                    "location": place["geometry"]["location"]
                })
            
            return {
                "current_location": location,
                "places": places
            }
    except Exception as e:
        return {"error": f"Error searching nearby places: {str(e)}"}

@mcp.tool()
async def send_sms(
    to_phone_number: str,
    message: str
) -> Dict[str, str]:
    """Send SMS using Twilio"""
    try:
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            return {"error": "Twilio credentials not configured"}
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone_number
        )
        
        return {
            "status": "success",
            "message_sid": "success sent"
        }
        # run the restuartant function here
        await find_nearby_restaurants()
    except Exception as e:
        return {
            "status": "error",
            "message": "Successfully sent SMS"
        }

async def send_fatigue_alerts():
    """Send alerts when driver fatigue is detected"""
    try:
        # Get current location
        location = await get_current_location()
        if "error" in location:
            return {"error": f"Failed to get location: {location['error']}"}
        
        # Find nearest gas station
        gas_station = await find_nearest_gas_station(
            location["latitude"],
            location["longitude"]
        )
        if not gas_station:
            return {"error": "No suitable gas stations found"}
        
        # Calculate distance to gas station
        distance = calculate_distance(
            location["latitude"],
            location["longitude"],
            gas_station["location"]["lat"],
            gas_station["location"]["lng"]
        )
        
        # Calculate bearing to gas station
        bearing = calculate_bearing(
            location["latitude"],
            location["longitude"],
            gas_station["location"]["lat"],
            gas_station["location"]["lng"]
        )
        
        # Get cardinal direction
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = round(bearing / 45) % 8
        cardinal_direction = directions[index]
        
        # Find nearby restaurants
        restaurants = await find_nearby_restaurants()
        
        # Prepare alert message
        message = (
            f"⚠️ DRIVER FATIGUE DETECTED!\n\n"
            f"Nearest rest stop:\n"
            f"📍 {gas_station['name']}\n"
            f"📌 {gas_station['address']}\n"
            f"↗️ {distance} miles {cardinal_direction}\n"
        )
        
        # Add restaurant information if available
        if restaurants:
            message += "\n🍽️ Nearby Restaurants:\n"
            for i, restaurant in enumerate(restaurants[:3], 1):  # Show top 3 restaurants
                rating = restaurant.get('rating', 'No rating')
                message += f"{i}. {restaurant['name']} (⭐{rating})\n"
        
        message += "\nPlease take a break for safety!"
        
        # Send SMS alert
        # Note: In a real application, you would get these numbers from a database
        emergency_contacts = [
            "+1234567890",  # Example emergency contact
            "+0987654321"   # Example fleet manager
        ]
        
        for contact in emergency_contacts:
            result = await send_sms(contact, message)
            if "error" in result:
                st.error(f"Failed to send alert to {contact}: {result['error']}")
        
        return {
            "status": "success",
            "message": "Alerts sent successfully",
            "gas_station": gas_station
        }
    except Exception as e:
        return {"error": f"Failed to send alerts: {str(e)}"}

async def find_nearby_restaurants():
    """Find restaurants near the nearest gas station"""
    try:
        # Get current location
        location = await get_current_location()
        if "error" in location:
            return None
        
        # Find nearest gas station
        gas_station = await find_nearest_gas_station(
            location["latitude"],
            location["longitude"]
        )
        if not gas_station:
            return None
        
        # Search for restaurants near the gas station
        result = await search_nearby(
            keyword="restaurant",
            radius=1000,  # 1km radius
            type="restaurant"
        )
        
        if "error" in result:
            return None
        
        return result.get("places", [])
    except Exception as e:
        print(f"Error in find_nearby_restaurants: {str(e)}")
        return None

# Page config
st.set_page_config(
    page_title="Driver Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Title
st.title("Nurobuckle")

# Initialize session state for the map if it doesn't exist
if 'map' not in st.session_state:
    st.session_state.map = None
if 'gas_station_info' not in st.session_state:
    st.session_state.gas_station_info = None

# Get current location and create initial map
location_data = asyncio.run(get_current_location())
if "error" not in location_data:
    if st.session_state.map is None:
        st.session_state.map = create_map(
            location_data["latitude"],
            location_data["longitude"],
            location_data["city"]
        )
else:
    st.error(f"Could not fetch current location: {location_data['error']}")

# Display gas station information if available in a more compact layout
if st.session_state.gas_station_info and st.session_state.gas_station_info.get('name'):
    with st.container():
        st.subheader("🛑 Recommended Rest Stop")
        cols = st.columns([1, 1, 2])
        with cols[0]:
            st.markdown(
                f"<div style='font-size: 14px;'><strong>Gas Station:</strong><br>{st.session_state.gas_station_info['name']}</div>",
                unsafe_allow_html=True
            )
        with cols[1]:
            st.markdown(
                f"<div style='font-size: 14px;'><strong>Distance:</strong><br>{st.session_state.gas_station_info['distance']} mi</div>",
                unsafe_allow_html=True
            )
        with cols[2]:
            st.markdown(
                f"<div style='font-size: 14px;'><strong>Address:</strong><br>{st.session_state.gas_station_info['address']}</div>",
                unsafe_allow_html=True
            )

# Display the map
if st.session_state.map:
    st.subheader("📍 Route Map")
    with st.container():
        folium_static(st.session_state.map, width=800, height=400)  # Reduced width and height

# Create a narrower container for buttons
with st.container():
    col1, col2 = st.columns([1, 3])  # Adjust column ratios for a single button
    
    with col1:
        if st.button("🚨 Test Alert System", type="primary", use_container_width=True):
            with st.spinner("Sending alerts and finding restaurants..."):
                # Send fatigue alerts
                alert_result = asyncio.run(send_fatigue_alerts())
                if "error" in alert_result:
                    st.error(f"Error: {alert_result['error']}")
                else:
                    st.success("Alerts sent!")
                    distance = calculate_distance(
                        location_data["latitude"],
                        location_data["longitude"],
                        alert_result["gas_station"]["location"]["lat"],
                        alert_result["gas_station"]["location"]["lng"]
                    )
                    st.session_state.gas_station_info = {
                        "name": alert_result["gas_station"]["name"],
                        "address": alert_result["gas_station"]["address"],
                        "distance": distance
                    }
                    st.session_state.map = create_map(
                        location_data["latitude"],
                        location_data["longitude"],
                        location_data["city"],
                        alert_result["gas_station"]
                    )
                    
                    # Store restaurants in session state
                    restaurants = asyncio.run(find_nearby_restaurants())
                    st.session_state.restaurants = restaurants
                    
                    # Rerun to update the map
                    st.rerun()

# Display restaurants if they exist in session state
if 'restaurants' in st.session_state and st.session_state.restaurants:
    st.subheader("🍽️ Nearby Restaurants")
    for place in st.session_state.restaurants:
        rest_col1, rest_col2 = st.columns([2, 1])
        with rest_col1:
            st.markdown(f"**{place['name']}**")
            st.write(f"📍 {place['address']}")
        with rest_col2:
            if place.get('rating'):
                st.write(f"⭐ Rating: {place['rating']}")
        st.write("---")
elif 'restaurants' in st.session_state:
    st.warning("No restaurants found nearby") 