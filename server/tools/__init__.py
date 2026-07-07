from .weather import get_weather
from .search import web_search
from .product_hunt import product_hunt_search
from .places import search_nearby_businesses

TOOLS = [get_weather, web_search, product_hunt_search, search_nearby_businesses]
