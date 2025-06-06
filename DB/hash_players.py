import csv
import bcrypt
import re

# Read the CSV file. This file has been removed from the VM for security
with open('2425_game_players.csv', newline='', encoding='utf-8-sig') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        firstname = row['first_name']
        lastname = row['last_name']
        email = row['email_address']

        username = (firstname[0] + re.sub(r'[^a-zA-Z]', '', lastname)).lower()
        password = email.split("@")[0]
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Generate SQL insert statement
        print(f"INSERT INTO players (firstname, lastname, username, password_hash) VALUES ('{firstname}', '{lastname}', '{username}', '{hashed}');")
