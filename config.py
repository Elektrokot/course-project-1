from pathlib import Path
from environs import env

env.read_env()

API_KEY = "API_KEY_ALPHAVANTAGE"
PATH = Path(__file__).parent
PATH_TO_OPERATIONS = PATH / "data" / "operations.xlsx"
PATH_TO_USER_SETTINGS = PATH / "user_settings.json"
PATH_TO_LOGGER = PATH / "logs"
