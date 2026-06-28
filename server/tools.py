import httpx
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get the current weather for a specific location.
    
    Args:
        location: The city and state/country, e.g., "San Francisco, CA" or "Tokyo"
    """
    # Open-Meteo Geocoding API to get coordinates
    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
    
    with httpx.Client() as client:
        geo_response = client.get(geocode_url)
        geo_data = geo_response.json()
        
        if not geo_data.get("results"):
            return f"Could not find coordinates for {location}."
            
        result = geo_data["results"][0]
        lat, lon = result["latitude"], result["longitude"]
        name = result["name"]
        
        # Open-Meteo Weather Forecast API
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m&temperature_unit=celsius"
        weather_response = client.get(weather_url)
        weather_data = weather_response.json()
        
        current = weather_data.get("current", {})
        temp = current.get("temperature_2m", "Unknown")
        wind = current.get("wind_speed_10m", "Unknown")
        
        return f"Current weather in {name}: {temp}°C, wind speed {wind} km/h."

@tool
def check_email() -> str:
    """Check the user's email inbox for recent unread messages."""
    # Mock email implementation
    emails = [
        {"from": "boss@company.com", "subject": "Urgent: Project Update", "snippet": "Please send the latest status report by EOD."},
        {"from": "newsletter@techdaily.com", "subject": "Top 10 AI Frameworks in 2026", "snippet": "Check out the latest tools for building AI agents..."},
        {"from": "noreply@github.com", "subject": "[GitHub] Please review PR #42", "snippet": "Alice has requested your review on the cortex-ai repository."},
    ]
    
    response = "You have 3 unread emails:\n\n"
    for idx, email in enumerate(emails, 1):
        response += f"{idx}. From: {email['from']}\n   Subject: {email['subject']}\n   Preview: {email['snippet']}\n\n"
        
    return response

TOOLS = [get_weather, check_email]
