import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FOUNDRY_ENDPOINT = os.environ["FOUNDRY_ENDPOINT"]
MODEL_DEPLOYMENT_NAME = os.environ["MODEL_DEPLOYMENT_NAME"]
APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
