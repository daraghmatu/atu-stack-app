from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
import bcrypt
from dotenv import load_dotenv
import os
import random
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_KEY')

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MySQL connection
db = mysql.connector.connect(
    host=os.getenv('MYSQL_HOST'),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PWD'),
    database=os.getenv('MYSQL_SCHEMA')
)
cursor = db.cursor(dictionary=True)

# ---- User Class ----
class User(UserMixin):
    def __init__(self, id, firstname):
        self.id = id
        self.firstname = firstname

# ---- User Loader ----
@login_manager.user_loader
def load_user(user_id):
    cursor.execute("SELECT * FROM players WHERE player_id = %s", (user_id,))
    user = cursor.fetchone()
    if user:
        #return User(id=user['id'], firstname=user['first_name'])
        return User(id=user['player_id'], firstname=user['firstname'])
    return None

# ---- Routes ----

# Main routes
@app.route('/')
def index():
    return render_template('rules.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor.execute("SELECT * FROM players WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            user_obj = User(id=user['player_id'], firstname=user['firstname'])
            login_user(user_obj)
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out.")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Fetch player resources
    cursor.execute("""
        SELECT r.name, pr.quantity
        FROM player_resources pr
        JOIN resources r ON pr.resource_id = r.resource_id
        WHERE pr.player_id = %s
    """, (current_user.id,))
    resources = cursor.fetchall()

    # Fetch player credits
    cursor.execute("""
        SELECT credits
        FROM players
        WHERE player_id = %s
    """, (current_user.id,))
    result = cursor.fetchone()
    credits = result['credits']

    # Fetch player history
    cursor.execute("""
        SELECT action_type, description, credits_earned, timestamp
        FROM player_history
        WHERE player_id = %s
        ORDER BY timestamp DESC
        LIMIT 10
    """, (current_user.id,))
    history = cursor.fetchall()

    # Player Rank
    cursor.execute("""
        SELECT COUNT(*) + 1 as p_rank
        FROM players
        WHERE credits > (
            SELECT credits FROM players WHERE player_id = %s
        )
    """, (current_user.id,))
    result = cursor.fetchone()
    rank = result['p_rank']
    
    return render_template('dashboard.html', resources=resources, credits=credits, history=history, rank=rank)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    # ***************** In production you'd check for admin role here
    if request.method == 'POST':
        if 'isolation_level' in request.form:
            level = request.form['isolation_level']
            cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {level}")
            db.commit()
            flash(f"Isolation level set to {level}")
        elif request.form.get('toggle_round') == 'start':
            flash("Round started.")
        elif request.form.get('toggle_round') == 'stop':
            flash("Round stopped.")
    return render_template('admin.html')

@app.route('/actions')
@login_required
def actions():
    return render_template('actions.html')

# Action routes
@app.route('/actions/collect', methods=['GET'])
@login_required
def show_collect_page():
    player_id = current_user.id

    # Get last collect time + num collects
    cursor.execute("""
        SELECT MAX(timestamp) as tm, MAX(collect_num) as cn
        FROM collect_log
        WHERE player_id = %s
    """, (player_id,))
    last_collect = cursor.fetchone()

    last_time = last_collect['tm']
    collect_count = last_collect['cn'] or 0
    hangover_chance = min(max(collect_count * 5, 0), 25)

    # Block if too early
    if last_time:
        if datetime.now() - last_time < timedelta(seconds=30):
            flash("⏳ You must wait 30 seconds between collections.", "warning")
            return redirect(url_for('dashboard'))

    return render_template("actions/collect.html",
                           hangover_chance=hangover_chance,
                           collect_count=collect_count)

@app.route('/actions/collect/confirm', methods=['POST'])
@login_required
def perform_collect():
    player_id = current_user.id

    # Get last collect time + num collects
    cursor.execute("""
        SELECT MAX(collect_num) as cn
        FROM collect_log
        WHERE player_id = %s
    """, (player_id,))
    last_collect = cursor.fetchone()
    collect_count = last_collect['cn'] or 0

    # Determine hangover chance
    hangover_chance = min(max(collect_count * 5, 0), 25)
    got_hangover = random.randint(1, 100) <= hangover_chance

    if got_hangover:
		# Halve player resources
        cursor.execute("""
            UPDATE player_resources
            SET quantity = FLOOR(quantity / 2)
            WHERE player_id = %s
        """, (player_id,))
        db.commit()

        cursor.execute("""
            INSERT INTO player_history (player_id, action_type, description, timestamp)
            VALUES (%s, 'hangover', '😵 Hangover! Resources halved.', NOW())
        """, (player_id,))
        db.commit()

        flash("😵 Oh no! Hangover. Your resources were halved.", "danger")
    else:
		# Pick random resoource
        cursor.execute("SELECT resource_id, name FROM resources")
        resources = cursor.fetchall()
        chosen = random.choice(resources)
        res_id = chosen['resource_id']
        res_name = chosen['name']

		# Plus one to resource
        cursor.execute("""
            INSERT INTO player_resources (player_id, resource_id, quantity)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE quantity = quantity + 1
        """, (player_id, res_id))
        db.commit()

        description = f'Collected 1x {res_name}'

        if res_name == 'pizza':
            description = description + ' 🍕'
        elif res_name == 'coffee':
            description = description + ' ☕'
        elif res_name == 'sleep':
            description = description + ' 😴'
        elif res_name == 'study':
            description = description + ' 📖'

        cursor.execute("""
            INSERT INTO player_history (player_id, action_type, description, timestamp)
            VALUES (%s, 'collect', %s, NOW())
        """, (player_id, description))
        db.commit()

        flash(f"🍀 You collected 1x {res_name}!", "success")

    # Log collect with incremented collect number
    cursor.execute("""
        INSERT INTO collect_log (player_id, collect_num, timestamp)
        VALUES (%s, %s, NOW())
    """, (player_id, collect_count + 1))
    db.commit()

    return redirect(url_for('dashboard'))

@app.route('/actions/submit')
@login_required
def submit():
    return render_template('actions/submit.html')


@app.route('/actions/trade')
@login_required
def trade():
    return render_template('actions/trade.html')

@app.route('/actions/leaderboard')
@login_required
def leaderboard():
    cursor.execute("""
        SELECT firstname, lastname, credits
        FROM players
        ORDER BY credits DESC, lastname
    """)
    leaderboard = cursor.fetchall()
    return render_template('actions/leaderboard.html', leaderboard=leaderboard)

# ---- Run ----
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
    # app.run(debug=False, host='0.0.0.0', port=5000)