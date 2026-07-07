"""
places.py

LangChain tool: search_nearby_businesses
Searches for businesses near the user's current location using the
Google Places API (New) – Text Search endpoint.

The user's Google OAuth access token and GPS coordinates are injected at
invocation time via the LangChain RunnableConfig (config["configurable"]).
This is the same token already flowing through the Cortex-AI pipeline
for Gmail access, so no extra credential plumbing is required.
"""

import httpx
import logging
from typing import Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

# Google Places API (New) – Text Search (supports textQuery + locationBias circle)
PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Fields returned per place (FieldMask).  Keep this targeted to avoid
# billing for fields the agent never uses.
FIELD_MASK = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.rating",
    "places.userRatingCount",
    "places.primaryTypeDisplayName",
    "places.regularOpeningHours",
    "places.priceLevel",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.googleMapsUri",
])

PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": "Free",
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}


@tool
def search_nearby_businesses(
    query: str,
    radius_meters: Optional[int] = 1500,
    max_results: Optional[int] = 10,
    config: RunnableConfig = None,
) -> str:
    """Search for businesses or places near the user's current GPS location
    using Google Places API.

    Use this tool whenever the user asks about nearby places, restaurants,
    shops, services, or any location-based business query such as:
    - "Find coffee shops near me"
    - "What restaurants are close by?"
    - "Is there a pharmacy near my location?"
    - "Search for gyms within 1 km"

    The mobile app supplies the user's GPS coordinates automatically — do not
    ask the user for latitude or longitude.

    Args:
        query: A text query describing what to search for (e.g., "pizza restaurant",
               "coffee shop", "pharmacy", "atm").
        radius_meters: Search radius in meters (default 1500, max 50000).
        max_results: Maximum number of results to return (default 10, max 20).
    """
    cfg = (config or {}).get("configurable", {})
    google_access_token: str | None = cfg.get("google_access_token")
    latitude = cfg.get("latitude")
    longitude = cfg.get("longitude")

    if latitude is None or longitude is None:
        return (
            "Error: Location not available. "
            "Please enable location permissions in the app and try again."
        )

    if not google_access_token:
        return (
            "Error: No Google access token was provided. "
            "Please sign in with Google so the app can access location services."
        )

    # ── Clamp inputs to API limits ───────────────────────────────────────────────
    radius_meters = max(1, min(radius_meters or 1500, 50_000))
    max_results = max(1, min(max_results or 10, 20))

    # ── Build the Nearby Search request ─────────────────────────────────────────
    headers = {
        "Authorization": f"Bearer {google_access_token}",
        "Content-Type": "application/json",
        "X-Goog-FieldMask": FIELD_MASK,
    }

    payload = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": float(radius_meters),
            }
        },
        "pageSize": max_results,
        "languageCode": "en",
    }

    # ── Call the API ─────────────────────────────────────────────────────────────
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                PLACES_TEXT_SEARCH_URL,
                headers=headers,
                json=payload,
            )

        if response.status_code == 401:
            return (
                "Error: Google access token is invalid or expired. "
                "Please re-authenticate and try again."
            )

        if response.status_code == 403:
            return (
                "Error: Access denied by Google Places API. "
                "Ensure the Google Places API (New) is enabled in your Google Cloud project "
                "and that your OAuth scopes include 'https://www.googleapis.com/auth/cloud-platform'."
            )

        if response.status_code != 200:
            logger.error(
                "Places API error %s: %s",
                response.status_code,
                response.text[:500],
            )
            return f"Google Places API returned an error (HTTP {response.status_code}). Please try again later."

        data = response.json()
        places = data.get("places", [])

        if not places:
            return (
                f"No results found for '{query}' within {radius_meters} m of your location. "
                "Try broadening the search radius or using a different query."
            )

        # ── Format results ───────────────────────────────────────────────────────
        lines: list[str] = [
            f"## Nearby '{query}' – {len(places)} result(s) within {radius_meters} m\n"
        ]

        for idx, place in enumerate(places, 1):
            name = place.get("displayName", {}).get("text", "Unknown")
            address = place.get("formattedAddress", "Address not available")
            rating = place.get("rating")
            review_count = place.get("userRatingCount")
            place_type = place.get("primaryTypeDisplayName", {}).get("text", "")
            price_key = place.get("priceLevel", "")
            price = PRICE_LEVEL_MAP.get(price_key, "")
            website = place.get("websiteUri", "")
            phone = place.get("nationalPhoneNumber", "")
            maps_url = place.get("googleMapsUri", "")

            # Opening hours
            opening_hours = place.get("regularOpeningHours", {})
            open_now = opening_hours.get("openNow")
            if open_now is True:
                hours_status = "✅ Open now"
            elif open_now is False:
                hours_status = "❌ Closed now"
            else:
                hours_status = ""

            # Build the entry
            entry = f"### {idx}. {name}"
            if place_type:
                entry += f" *(#{place_type})*"
            entry += "\n"
            entry += f"📍 {address}\n"

            if rating:
                stars = "⭐" * round(rating)
                entry += f"{stars} {rating:.1f}"
                if review_count:
                    entry += f" ({review_count:,} reviews)"
                entry += "\n"

            if price:
                entry += f"💰 Price: {price}\n"

            if hours_status:
                entry += f"{hours_status}\n"

            if phone:
                entry += f"📞 {phone}\n"

            if website:
                entry += f"🌐 {website}\n"

            if maps_url:
                entry += f"🗺️ [Open in Google Maps]({maps_url})\n"

            lines.append(entry)

        return "\n".join(lines)

    except httpx.TimeoutException:
        return "Request to Google Places API timed out. Please try again."
    except Exception as exc:
        logger.exception("Unexpected error in search_nearby_businesses: %s", exc)
        return f"An unexpected error occurred while searching for nearby businesses: {exc}"
