from .weather import get_weather
from .email import check_email
from .search import web_search
from .drive import read_drive_file

# List of all available tools for the agent
TOOLS = [get_weather, check_email, web_search, read_drive_file]
