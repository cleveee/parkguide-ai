"""Run real configured chat from this checkout, with an optional external .env."""
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--env-file', type=Path, default=Path(__file__).resolve().parents[1] / '.env')
parser.add_argument('--port', type=int, default=8537)
args = parser.parse_args()
if not args.env_file.is_file():
    parser.error('The environment file is missing. Pass --env-file with the existing project .env path.')
load_dotenv(args.env_file, override=False)
os.environ['PARKGUIDE_WEB_PORT'] = str(args.port)

from parkguide.web import main

main()
