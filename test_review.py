import json
import sys
from pathlib import Path

# Ensure project dir is on sys.path (like app.py does)
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR / "contract-review-bot"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from importlib import import_module
# import main.py from the project directory
try:
    review_contract = import_module("main").review_contract
except ModuleNotFoundError:
    review_contract = import_module("contract_review_bot.main").review_contract

try:
    report = review_contract('This is a test contract between Acme Robotics Inc. and Beta Logistics LLC. Confidential information included.')
    print('OK', type(report))
    print(json.dumps(report, indent=2)[:2000])
except Exception as e:
    print('ERROR', e)
