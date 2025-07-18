from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
import bcrypt
from dotenv import load_dotenv
import os

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
        SELECT action_type, details, credits_earned, timestamp
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
    # In production you'd check for admin role here
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
@app.route('/actions/collect')
@login_required
def collect():
    return render_template('actions/collect.html')


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