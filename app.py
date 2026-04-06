from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import psycopg2
import bcrypt
import os
import requests

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_key")

# -----------------------------
# DATABASE CONNECTION
# -----------------------------
def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))
# -----------------------------
# for saving previous messages
# -----------------------------
def save_message(user_id, role, content):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_messages (user_id, role, content)
        VALUES (%s, %s, %s)
        """,
        (user_id, role, content)
    )
    conn.commit()
    cur.close()
    conn.close()
# -----------------------------
# fetching user messages
# -----------------------------
def get_conversation(user_id, limit=10):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT role, content
        FROM chat_messages
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, limit)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    rows.reverse()  # restore correct order
    return [{"role": r[0], "content": r[1]} for r in rows]

# -----------------------------
# helper functions
# -----------------------------
def update_summary(user_id, new_summary):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET conversation_summary = %s
        WHERE id = %s
        """,
        (new_summary, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_summary(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT conversation_summary
        FROM users
        WHERE id = %s
        """,
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    return row[0] if row and row[0] else None



# -----------------------------
# LANDING
# -----------------------------
@app.route('/')
def landing():
    
    return render_template('landing.html')

# -----------------------------
# REGISTER
# -----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (username, email, hashed_password)
            )
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return "Email already registered"
        finally:
            cur.close()
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

# -----------------------------
# LOGIN
# -----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, password_hash FROM users WHERE email = %s",
            (email,)
        )
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and bcrypt.checkpw(
            password.encode('utf-8'),
            user[1].encode('utf-8')
        ):
            session['user_id'] = user[0]
            return redirect(url_for('index'))   # ✅ FIXED
        else:
            return "Invalid email or password"

    return render_template('login.html')

# -----------------------------
# CHATBOT PAGE
# -----------------------------
@app.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

# -----------------------------
# LOGOUT
# -----------------------------
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# -----------------------------
# OPENROUTER AI FUNCTION
# -----------------------------
def ask_openrouter(messages):
    api_key = os.getenv("OPENROUTER_API_KEY")

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-3.5-turbo",
            "messages": messages,
            "max_tokens": 300
        }
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# -----------------------------
# summary CONNECTION
# -----------------------------
def summarize_conversation(messages):
    api_key = os.getenv("OPENROUTER_API_KEY")

    summary_prompt = [
        {
            "role": "system",
            "content": "Summarize the following conversation briefly, preserving important facts, names, and context."
        }
    ] + messages

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-3.5-turbo",
            "messages": summary_prompt,
            "max_tokens": 200
        }
    )

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]

# -----------------------------
# CHAT API (THIS FIXES JS)
# -----------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    # 1️⃣ Save current user message
    save_message(user_id, "user", user_message)

    # 2️⃣ Fetch LAST messages (now correct)
    recent_messages = get_conversation(user_id, limit=8)

    # 3️⃣ Fetch summary
    summary = get_summary(user_id)

    # 4️⃣ Build prompt
    messages_for_ai = [
        {"role": "system", "content": "You are a helpful AI chatbot."}
    ]

    if summary:
        messages_for_ai.append({
            "role": "system",
            "content": (
                "Use the following summary only as background context. "
                "Ignore it if the user's question is unrelated.\n\n"
                f"Summary: {summary}"
            )
        })

    messages_for_ai.extend(recent_messages)

    

    # 5️⃣ Ask AI
    ai_reply = ask_openrouter(messages_for_ai)

    # 6️⃣ Save AI reply
    save_message(user_id, "assistant", ai_reply)

    return jsonify({"reply": ai_reply})


    

# -----------------------------
# RUN APP
# -----------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
