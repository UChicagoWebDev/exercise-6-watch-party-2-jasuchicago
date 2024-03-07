import string
import random
import sqlite3
from datetime import datetime
from flask import * # Flask, g, redirect, render_template, request, url_for
from functools import wraps

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

def get_db():
    db = getattr(g, '_database', None)

    if db is None:
        db = g._database = sqlite3.connect('db/watchparty.sqlite3')
        db.row_factory = sqlite3.Row
        setattr(g, '_database', db)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    db = get_db()
    cursor = db.execute(query, args)
    rows = cursor.fetchall()
    db.commit()
    cursor.close()
    if rows:
        if one:
            return rows[0]
        return rows
    return None

def new_user():
    name = "Unnamed User #" + ''.join(random.choices(string.digits, k=6))
    password = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    api_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=40))
    u = query_db('insert into users (name, password, api_key) ' +
        'values (?, ?, ?) returning id, name, password, api_key',
        (name, password, api_key),
        one=True)
    return u

# TODO: If your app sends users to any other routes, include them here.
#       (This should not be necessary).
# Define the root route and several other routes that will serve the same static HTML file
@app.route('/')
@app.route('/profile')
@app.route('/login')
@app.route('/room')
@app.route('/room/<chat_id>')
def index(chat_id=None):  # 'chat_id' is optional and defaults to None
 # Serve the 'index.html' static file to the client for these routes
    return app.send_static_file('index.html')

# Define a custom error handler for 404 errors (page not found)
@app.errorhandler(404)
def page_not_found(e):
    return app.send_static_file('404.html'), 404

# -------------------------------- API ROUTES ----------------------------------

# TODO: Create the API

# Define a route for the signup process, accepting POST requests
@app.route('/api/signup', methods=['POST'])
def signUp():
    new_user_data = new_user()
    
    if not new_user_data:
        return jsonify({"error": "Failed to create user"}), 500

    return jsonify({
        "user_id": new_user_data["id"],
        "user_name": new_user_data["name"],
        "api_key": new_user_data["api_key"],
    }), 200   

# Define a route for the login process, accepting POST requests
@app.route('/api/login', methods=['POST'])
def logIn():
    data = request.json
    user_name = data.get('user_name')
    password = data.get('password')
    if not user_name or not password:
        return jsonify({"error": "Username and password are required"}), 400
    
    user = query_db('SELECT * FROM users WHERE name = ? and password = ?', [user_name, password], one=True)
    
    if user:        
        return jsonify({
            "user_id": user["id"],
            "user_name": user["name"],
            "api_key": user["api_key"],
        }), 200
    
    return jsonify({"error": "Invalid credentials"}), 401

# Decorator to enforce API key requirement for certain routes
def require_api_key(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('Authorization')
        print("Received API Key:", api_key)
        if not api_key:
            return jsonify({"error": "API key required"}), 403  
        
        user = query_db('SELECT * FROM users WHERE api_key = ?', [api_key], one=True)
        print("User found:", user)
        if not user:
            return jsonify({"error": "Invalid API key"}), 403  
        return func(*args, **kwargs)
    return decorated_function

# Define a route for updating a user's name, accepting POST requests and requiring an API key
@app.route('/api/user/name', methods=['POST'])
@require_api_key
def update_username():
    data = request.json
    new_name = data.get('new_name')
    if not new_name:
        return jsonify({"error": "New username is required"}), 400
    
    api_key = request.headers.get('Authorization')
    query_db('UPDATE users SET name = ? WHERE api_key = ?', [new_name, api_key])
    
    return jsonify({"message": "Username updated successfully"}), 200

# Define a route for changing a user's password, accepting POST requests and requiring an API key
@app.route('/api/user/password', methods=['POST'])
@require_api_key
def update_password():
    data = request.json
    new_password = data.get('new_password')
    if not new_password:
        return jsonify({"error": "New password is required"}), 400
    
    api_key = request.headers.get('Authorization')
    query_db('UPDATE users SET password = ? WHERE api_key = ?', [new_password, api_key])
   
    return jsonify({"message": "Password updated successfully"}), 200

# Define a route for creating a new room, accepting POST requests and requiring an API key
@app.route('/api/rooms/new', methods = ['POST'])
@require_api_key
def create_room():
    name = "Unnamed Room " + ''.join(random.choices(string.digits, k=6))
    room = query_db('INSERT INTO rooms (name) VALUES (?) RETURNING id', [name], one=True)
    
    if not room:
        return jsonify({"error": "Failed to create room"}), 500
    
    return jsonify({
        'id': room['id'],
        'name': name,
    }), 200   

# Define a route for retrieving all rooms, accepting GET requests and requiring an API key
@app.route('/api/rooms', methods = ['GET'])
@require_api_key
def get_all_room():
    rooms = query_db('SELECT * FROM rooms')
    room_list = [{"room_id": room["id"], "room_name": room["name"]} for room in rooms]
    return jsonify(room_list), 200 

# Define a route for retrieving the name of a specific room, accepting GET requests and requiring an API key
@app.route('/api/rooms/<int:room_id>', methods = ['GET'])
@require_api_key
def get_room_name(room_id):
    room = query_db('SELECT * FROM rooms WHERE id = ?', [room_id], one=True)
    
    if not room:
        return jsonify({"error": "Room not found"}), 404
    
    return jsonify({"room_id": room["id"], "room_name": room["name"]}), 200    

# Define a route for updating a room's name, accepting POST requests and requiring an API key
@app.route('/api/rooms/name', methods=['POST'])
@require_api_key
def change_room_name():
    data = request.json
    new_name = data.get('new_name')
    room_id = data.get('room_id')
    if not new_name or not room_id:
        return jsonify({"error": "New room name and room ID are required"}), 400
    
    query_db('UPDATE rooms SET name = ? WHERE id = ?', [new_name, room_id])
    
    return jsonify({"message": "Room name updated successfully"}), 200

# Define a route for retrieving messages in a specific room, accepting GET requests and requiring an API key
@app.route('/api/rooms/<int:room_id>/messages', methods=['GET'])
@require_api_key
def get_messages(room_id):
    messages = query_db('''
        SELECT messages.id, users.name AS author, messages.body
        FROM messages
        JOIN users ON messages.user_id = users.id
        WHERE room_id = ?''',
        [room_id])
    
    message_list = [{"id": msg["id"], "author": msg["author"], "body": msg["body"]} for msg in messages]
    #print(message_list)
    return jsonify(message_list), 200

# Define a route for posting a message in a specific room, accepting POST requests and requiring an API key
@app.route('/api/rooms/<int:room_id>/messages', methods=['POST'])
@require_api_key
def post_message(room_id):
    data = request.json
    user_id = data.get('user_id')
    body = data.get('body')
    if not user_id or not body:
        return jsonify({"error": "User ID and message body are required"}), 400
    
    query_db('INSERT INTO messages (user_id, room_id, body) VALUES (?, ?, ?)', [user_id, room_id, body])
    
    return jsonify({"message": "Message posted successfully"}), 200
