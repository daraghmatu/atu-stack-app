# ATU Stack Web App

This is a web-based simulation game designed for database learning and interaction.

## Purpose

The app allows students to log in, view their resource allocations, and interact with other players through trading. The backend is powered by a MySQL database to help illustrate key relational database concepts in a live environment.

## How to Use

- Instructor will start the web server during lectures
- Students will be given a public IP address to connect to
- Log in with assigned credentials
- Use the dashboard to monitor and interact

## Rules

- Each player starts with a random allocation of resources
- Players can trade resources with others
- Spend resources to complete tasks
- Earn as many 🎓 Credits as possible!
- Beware of the 🤢 Hangovers

## Tech Stack

- Python + Flask
- MySQL
- HTML (Jinja templates)
- Hosted manually via Flask for use in lectures

## Notes

This app prioritizes clarity of database operations over advanced Flask architecture. All code is contained in a single `app.py` file to support learning.
