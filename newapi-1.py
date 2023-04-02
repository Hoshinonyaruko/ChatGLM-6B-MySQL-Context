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
mysql.init_app(app)


def create_conversation(conversation_id):
    cursor = mysql.get_db().cursor()
    query = "INSERT INTO conversations (id) VALUES (%s)"
    cursor.execute(query, (conversation_id,))
    mysql.get_db().commit()


def add_message(conversation_id, parent_message_id, text, role):
    message_id = str(uuid.uuid4())
    cursor = mysql.get_db().cursor()
    query = "INSERT INTO messages (id, conversation_id, parent_message_id, text, role) VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(query, (message_id, conversation_id, parent_message_id, text, role))
    mysql.get_db().commit()
    print(f"Added message: {message_id}, role: {role}, text: {text}")  # Add debug information
    return message_id

def get_history(conversation_id, parent_message_id):
    cursor = mysql.get_db().cursor()
    query = "SELECT text, role FROM messages WHERE conversation_id = %s AND id <= %s ORDER BY created_at ASC"
    cursor.execute(query, (conversation_id, parent_message_id))
    rows = cursor.fetchall()
    history = []
    current_query = None
    for text, role in rows:
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

    user_message_id = add_message(conversation_id, parent_message_id, message_text, "user")

    history = []
    if parent_message_id:
        history = get_history(conversation_id, parent_message_id)
        print("history: " + str(history))

    # 调用API，并传入 history 参数
    response_text = call_chatgpt_api(prompt=message_text, history=history)

    assistant_message_id = add_message(conversation_id, user_message_id, response_text, "assistant")

    # 添加下面这行代码以将助手的回答存储到数据库中
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
