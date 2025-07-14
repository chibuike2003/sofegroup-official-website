import sys
import os

# Add the parent directory of your app.py to the Python path
# This assumes wsgi.py is in the same directory as app.py
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import your Flask application instance
# Assuming your Flask app is named 'app' in app.py
from app import app as application

# This 'application' variable is what WSGI servers look for.
# It should be the Flask app instance.
# If your Flask app instance is named differently (e.g., 'my_app'),
# change 'app as application' to 'my_app as application'.

# Example for Gunicorn:
# gunicorn wsgi:application

# Example for uWSGI:
# uwsgi --http :8000 --wsgi-file wsgi.py --callable application --master --processes 4 --threads 2
