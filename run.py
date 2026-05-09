from app import create_app
from dotenv import load_dotenv
import os  # <-- ADD THIS LINE

load_dotenv()

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=5000)