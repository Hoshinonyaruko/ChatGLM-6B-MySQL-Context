from flask import Flask, request, jsonify
from flaskext.mysql import MySQL
import uuid
import datetime
import requests

app = Flask(__name__)
mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = ''
app.config['MYSQL_DATABASE_DB'] = 'chatgpt'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_CHARSET'] = 'utf8mb4'
mysql.init_app(app)

MAX_TOKENS = 2048
def truncate_history(history, prompt):
    token_count = sum([len(entry[0]) + (len(entry[1]) if entry[1] else 0) for entry in history]) + len(prompt)
    if token_count <= MAX_TOKENS:
        return history
    
    # Step 1: Set assistant replies to None
    truncated_history = [(entry[0], None) for entry in history]
    token_count = sum([len(entry[0]) for entry in truncated_history]) + len(prompt)
    if token_count <= MAX_TOKENS:
        return truncated_history
    
    # Step 2: Remove history elements from the beginning until it fits within MAX_TOKENS
    while token_count > MAX_TOKENS:
        truncated_history.pop(0)
        token_count = sum([len(entry[0]) for entry in truncated_history]) + len(prompt)
    
    return truncated_history

def create_conversation(conversation_id):
    cursor = mysql.get_db().cursor()
    query = "INSERT INTO conversations (id) VALUES (%s)"
    cursor.execute(query, (conversation_id,))
    mysql.get_db().commit()


def add_message(conversation_id, parent_message_id, text, role):
    db = mysql.get_db()
    cursor = db.cursor()
    message_id = str(uuid.uuid4())

    query = """
        INSERT INTO messages (id, conversation_id, parent_message_id, text, role)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (message_id, conversation_id, parent_message_id, text, role))
    db.commit()
    return message_id

def get_history(conversation_id, parent_message_id):
    cursor = mysql.get_db().cursor()
    query = "SELECT text, role FROM messages WHERE conversation_id = %s AND id <= %s ORDER BY created_at ASC"
    cursor.execute(query, (conversation_id, parent_message_id))
    rows = cursor.fetchall()
    history = []
    current_query = None
    for text, role in rows:
        #text = text.decode('utf-8')
        if role == "user":
            if current_query is not None:
                history.append((current_query, None))
                current_query = text
            else:
                current_query = text
        else:  # role == "assistant"
            if current_query is not None:
                history.append((current_query, text))
                current_query = None
    if current_query is not None:
        history.append((current_query, None))
    return history

@app.route('/conversation', methods=['POST'])
def chat():
    data = request.get_json()
    message_text = data.get("message")
    conversation_id = data.get("conversationId")
    parent_message_id = data.get("parentMessageId")

    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        create_conversation(conversation_id)
        parent_message_id = None

    user_message_id = add_message(conversation_id, parent_message_id, message_text, "user")

    history = []
    if parent_message_id:
        history = get_history(conversation_id, parent_message_id)
        print("history: " + str(history))

        # Truncate history to fit within token limit
        history = truncate_history(history, message_text)
        print("truncated history: " + str(history))

    response_text = call_chatgpt_api(prompt=message_text, history=history)

    assistant_message_id = add_message(conversation_id, user_message_id, response_text, "assistant")

    add_message(conversation_id, assistant_message_id, response_text, "assistant")

    response = {
        "response": response_text,
        "conversationId": conversation_id,
        "messageId": assistant_message_id
    }
    return jsonify(response)

def call_chatgpt_api(prompt, history):
    url = "http://127.0.0.1:8000"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "prompt": prompt,
        "history": history
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        response_data = response.json()
        print(f"API response: {response_data}")  # Add debug information
        return response_data["response"]
    else:
        raise Exception(f"API request failed with status code {response.status_code}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=46130,debug=True)
