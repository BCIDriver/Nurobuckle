from mcp.server.fastmcp import FastMCP
import httpx
from typing import Optional, Dict, Any
from twilio.rest import Client
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Create MCP server
mcp = FastMCP("NearbySearch")

async def get_current_location() -> Dict[str, Any]:
    """Get current location based on IP using ipapi.co"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://ipapi.co/json/")
            response.raise_for_status()
            data = response.json()
            return {
                "latitude": float(data["latitude"]),
                "longitude": float(data["longitude"]),
                "city": data.get("city"),
                "region": data.get("region"),
                "country": data.get("country_name")
            }
        except Exception as e:
            return {"error": str(e)}

# Tool to search nearby places
@mcp.tool()
async def search_nearby(
    keyword: str,
    radius: int = 1500,
    type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search for nearby places using Google Places API based on current IP location.

    Args:
        keyword (str): The search term to look for (e.g., "coffee shop", "restaurant")
        radius (int, optional): Search radius in meters. Defaults to 1500
        type (str, optional): Specific type of place (e.g., "restaurant", "cafe"). See Google Places API docs for valid types

    Returns:
        Dict containing search results with place details
    """
    api_key = "AIzaSyDd1w5vqAmrcTe4C7kZsb5oZCjt2-3wXXw";
    if not api_key:
        return {"error": "GOOGLE_API_KEY environment variable is required"}

    # Get current location
    location_data = await get_current_location()
    if "error" in location_data:
        return location_data
    
    latitude = location_data["latitude"]
    longitude = location_data["longitude"]

    async with httpx.AsyncClient() as client:
        # Build Google Places Nearby Search URL
        base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{latitude},{longitude}",
            "radius": radius,
            "key": api_key,
        }
        if keyword:
            params["keyword"] = keyword
        if type:
            params["type"] = type
        
        try:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK":
                return {"error": data.get("status"), "message": data.get("error_message")}
            
            # Process and simplify results
            results = [
                {
                    "name": place["name"],
                    "address": place.get("vicinity"),
                    "location": place["geometry"]["location"],
                    "rating": place.get("rating"),
                    "types": place.get("types", [])
                }
                for place in data.get("results", [])
            ]
            return {
                "results": results,
                "count": len(results),
                "location": {"latitude": latitude, "longitude": longitude}
            }
        except Exception as e:
            return {"error": str(e)}
        


# Load environment variables
load_dotenv()

# Twilio credentials from .env
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Create MCP server
mcp = FastMCP("TwilioSMS")

@mcp.tool()
async def send_sms(
    to_phone_number: str,
    message: str
) -> Dict[str, str]:
    """
    Send an SMS message using Twilio.

    Args:
        to_phone_number (str): Recipient's phone number in E.164 format (e.g., +1234567890)
        message (str): Text message to send

    Returns:
        Dict containing message SID if successful or an error message
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        return {"error": "Missing Twilio credentials in environment variables."}
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone_number
        )
        return {"message_sid": msg.sid}
    except Exception as e:
        return {"error": str(e)}

# if __name__ == "__main__":
#     import asyncio
#     print(asyncio.run(send_sms("+13463916054", "Hello from Twilio!")))


# if __name__ == "__main__":
#     #mcp.run()
#     import asyncio
#     print(asyncio.run(search_nearby("restaurant")))