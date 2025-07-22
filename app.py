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
    database=os.getenv('MYSQL_SCHEMA'),
    autocommit=True     # mysql.connector py library will open connections with autocommit OFF by default
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
        # db.commit()   # not required with autocommit=True

        cursor.execute("""
            INSERT INTO player_history (player_id, action_type, description, timestamp)
            VALUES (%s, 'hangover', '😵 Hangover! Resources halved.', NOW())
        """, (player_id,))
        # db.commit()   # not required with autocommit=True

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
        # db.commit()   # not required with autocommit=True

        description = f'1x {res_name}'

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
        # db.commit()   # not required with autocommit=True

        flash(f"🍀 You collected 1x {res_name}!", "success")

    # Log collect with incremented collect number
    cursor.execute("""
        INSERT INTO collect_log (player_id, collect_num, timestamp)
        VALUES (%s, %s, NOW())
    """, (player_id, collect_count + 1))
    # db.commit()   # not required with autocommit=True

    return redirect(url_for('dashboard'))

@app.route('/actions/tasks', methods=['GET'])
@login_required
def submit_task_page():
    player_id = current_user.id

    # Get all tasks
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()

    # Get player's current resources
    cursor.execute("""
        SELECT r.name, pr.quantity
        FROM resources r
        LEFT JOIN player_resources pr 
        ON r.resource_id = pr.resource_id AND pr.player_id = %s
    """, (player_id,))
    resources = {row['name']: row['quantity'] or 0 for row in cursor.fetchall()}

    return render_template('actions/tasks.html', tasks=tasks, resources=resources)

@app.route('/actions/tasks', methods=['POST'])
@login_required
def perform_submit_task():
    player_id = current_user.id
    task_id = int(request.form['task_id'])

    # Get task costs and reward
    cursor.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
    task = cursor.fetchone()

    if not task:
        flash("❌ Invalid task selected.", "danger")
        return redirect(url_for('submit_task_page'))

    # Get player resources as a dictionary
    cursor.execute("""
        SELECT r.name, pr.quantity
        FROM resources r
        LEFT JOIN player_resources pr
        ON r.resource_id = pr.resource_id AND pr.player_id = %s
    """, (player_id,))
    player_resources = {row['name']: row['quantity'] or 0 for row in cursor.fetchall()}

    # Check if player has enough of each required resource
    requirements = {
        'pizza': task['pizza_cost'],
        'coffee': task['coffee_cost'],
        'sleep': task['sleep_cost'],
        'study': task['study_cost']
    }

    for res_name, cost in requirements.items():
        if player_resources.get(res_name, 0) < cost:
            flash(f"❌ Not enough {res_name}. You need {cost}.", "danger")
            return redirect(url_for('submit_task_page'))

    # Deduct resources
    for res_name, cost in requirements.items():
        cursor.execute("""
            UPDATE player_resources
            SET quantity = quantity - %s
            WHERE player_id = %s AND resource_id = (
                SELECT resource_id FROM resources WHERE name = %s
            )
        """, (cost, player_id, res_name))

    # Add credits
    cursor.execute("""
        UPDATE players
        SET credits = credits + %s
        WHERE player_id = %s
    """, (task['credit_reward'], player_id))

    # Log to history
    description = f"{task['name']} for {task['credit_reward']} credits 🎓"
    cursor.execute("""
        INSERT INTO player_history (player_id, action_type, description, timestamp)
        VALUES (%s, 'task', %s, NOW())
    """, (player_id, description))

    # db.commit()   # # not required with autocommit=True

    flash(f"✅ Task '{task['name']}' completed! You earned {task['credit_reward']} credits.", "success")
    return redirect(url_for('dashboard'))

@app.route('/actions/trade', methods=['GET', 'POST'])
@login_required
def trade():
    player_id = current_user.id
    
    if request.method == 'POST':
        recipient_id = int(request.form['recipient_id'])
        offered_resource_id = int(request.form['offered_resource_id'])
        requested_resource_id = int(request.form['requested_resource_id'])
        offered_quantity = int(request.form['offered_quantity'])
        requested_quantity = int(request.form['requested_quantity'])

        # Check initiator has enough offered resource
        cursor.execute("""
            SELECT quantity FROM player_resources
            WHERE player_id = %s AND resource_id = %s
        """, (player_id, offered_resource_id))
        result = cursor.fetchone()
        if not result or result['quantity'] < offered_quantity:
            flash("You do not have enough of that resource to offer.", "danger")
            return redirect(url_for('trade'))

        # Insert pending trade
        cursor.execute("""
            INSERT INTO trades (
                initiator_id, recipient_id,
                offered_resource_id, offered_quantity,
                requested_resource_id, requested_quantity
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            player_id, recipient_id,
            offered_resource_id, offered_quantity,
            requested_resource_id, requested_quantity
        ))
        # db.commit()   # not required with autocommit=True
        flash("Trade offer created.", "success")
        return redirect(url_for('trade'))

    # GET method — list other players and resources
    cursor.execute("SELECT player_id, firstname, lastname FROM players WHERE player_id != %s", (player_id,))
    other_players = cursor.fetchall()

    cursor.execute("SELECT resource_id, name FROM resources")
    resources = cursor.fetchall()

    return render_template('actions/trade.html', players=other_players, resources=resources)

@app.route('/actions/trade_offers')
@login_required
def trade_offers():
    player_id = current_user.id
    cursor.execute("""
        SELECT t.*, i.firstname AS initiator_firstname, i.lastname AS initiator_lastname,
               r1.name AS offered_resource, r2.name AS requested_resource
        FROM trades t
        JOIN players i ON t.initiator_id = i.player_id
        JOIN resources r1 ON t.offered_resource_id = r1.resource_id
        JOIN resources r2 ON t.requested_resource_id = r2.resource_id
        WHERE t.recipient_id = %s AND t.status = 'pending'
    """, (player_id,))
    offers = cursor.fetchall()
    return render_template('actions/trade_offers.html', offers=offers)

@app.route('/actions/accept_trade/<int:trade_id>', methods=['POST'])
@login_required
def accept_trade(trade_id):
    player_id = current_user.id
    try:
        db.start_transaction()      # *** Transaction started

        # Lock the trade row
        cursor.execute("""
            SELECT * FROM trades WHERE trade_id = %s AND status = 'pending' FOR UPDATE
        """, (trade_id,))
        trade = cursor.fetchone()
        if not trade or trade['recipient_id'] != player_id:
            db.rollback()           # *** Transaction ends if
            flash("Invalid or expired trade offer.", "danger")
            return redirect(url_for('trade_offers'))

        initiator_id = trade['initiator_id']
        offered_resource_id = trade['offered_resource_id']
        requested_resource_id = trade['requested_resource_id']
        offered_quantity = trade['offered_quantity']
        requested_quantity = trade['requested_quantity']

        # Lock initiator and recipient resource rows
        for pid, rid in [(initiator_id, offered_resource_id),
                         (initiator_id, requested_resource_id),
                         (player_id, offered_resource_id),
                         (player_id, requested_resource_id)]:
            cursor.execute("""
                SELECT quantity FROM player_resources
                WHERE player_id = %s AND resource_id = %s FOR UPDATE
            """, (pid, rid))
            cursor.fetchone()

        # Check both players have enough resources
        cursor.execute("""
            SELECT quantity FROM player_resources
            WHERE player_id = %s AND resource_id = %s
        """, (initiator_id, offered_resource_id))
        initiator_qty = cursor.fetchone()['quantity']

        cursor.execute("""
            SELECT quantity FROM player_resources
            WHERE player_id = %s AND resource_id = %s
        """, (player_id, requested_resource_id))
        recipient_qty = cursor.fetchone()['quantity']

        if initiator_qty < offered_quantity or recipient_qty < requested_quantity:
            db.rollback()       # *** Transaction ends if
            flash("One or both players lack required resources.", "danger")
            return redirect(url_for('trade_offers'))

        # Perform the exchange
        cursor.execute("""
            UPDATE player_resources SET quantity = quantity - %s
            WHERE player_id = %s AND resource_id = %s
        """, (offered_quantity, initiator_id, offered_resource_id))

        cursor.execute("""
            UPDATE player_resources SET quantity = quantity + %s
            WHERE player_id = %s AND resource_id = %s
        """, (offered_quantity, player_id, offered_resource_id))

        cursor.execute("""
            UPDATE player_resources SET quantity = quantity - %s
            WHERE player_id = %s AND resource_id = %s
        """, (requested_quantity, player_id, requested_resource_id))

        cursor.execute("""
            UPDATE player_resources SET quantity = quantity + %s
            WHERE player_id = %s AND resource_id = %s
        """, (requested_quantity, initiator_id, requested_resource_id))

        # Mark trade as completed
        cursor.execute("""
            UPDATE trades SET status = 'completed' WHERE trade_id = %s
        """, (trade_id,))

        db.commit()     # *** Transaction ends
        flash("Trade accepted and processed successfully.", "success")

    except Exception as e:
        db.rollback()   # *** Transaction ends except
        flash("Trade failed: " + str(e), "danger")
        
    return redirect(url_for('trade_offers'))
    
@app.route('/actions/reject_trade/<int:trade_id>', methods=['POST'])
@login_required
def reject_trade(trade_id):
    player_id = current_user.id
    cursor.execute("""
        UPDATE trades
        SET status = 'cancelled'
        WHERE trade_id = %s AND recipient_id = %s AND status = 'pending'
    """, (trade_id, player_id))
    # db.commit()   # not required with autocommit=True
    flash("Trade rejected.", "info")
    return redirect(url_for('trade_offers'))

@app.route('/actions/leaderboard')
@login_required
def leaderboard():
    cursor.execute(""" 
        SELECT 
            RANK() OVER (ORDER BY credits DESC) AS p_rank,
            firstname,
            lastname,
            credits
        FROM players
        ORDER BY p_rank, lastname;
    """)
    leaderboard = cursor.fetchall()
    return render_template('actions/leaderboard.html', leaderboard=leaderboard)

# ---- Run ----
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)