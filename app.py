import os
from hashlib import sha256
import sqlite3
from flask import Flask, make_response, render_template, request, abort
import pam

app = Flask(__name__)

# if users.db doesn't exist, create it
if not os.path.isfile('users.db'):
    open('users.db', 'w').close()

conn = sqlite3.connect('users.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        userhash TEXT NOT NULL
    )''')
conn.commit()
cursor.close()
conn.close()
del conn, cursor


@app.route('/')
def hello_world():  # put application's code here
    # find all folders in /srv/git that end with .git
    git_folders = []
    for folder_name in os.listdir('/srv/git'):
        folder_path = os.path.join('/srv/git', folder_name)
        if os.path.isdir(folder_path) and folder_name.endswith(".git"):
            git_folders.append(folder_path)
    return render_template('mainpage.html', amt_git=len(git_folders), hostname=os.uname()[1])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if pam.authenticate(request.form['username'], request.form['password']):
            resp = make_response("Success")
            resp.set_cookie('username', request.form['username'])
            resp.set_cookie('userhash', str(sha256(
                f"{request.form['username'][:1]} + {request.form['password']} + {request.form['username']}[1:]".encode(
                    'utf-8')).hexdigest()))
            cursor.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],))
            existing_user = cursor.fetchone()
            if existing_user is None:
                cursor.execute('INSERT INTO users (username, userhash) VALUES (?, ?)', (request.form['username'],
                                                                                        str(sha256(
                                                                                            f"username[:1] + password + username[1:]".encode(
                                                                                                'utf-8')).hexdigest())))
                conn.commit()
            return resp
        else:
            abort(403)

    return render_template('login.html')


@app.route('/authenticate/<username>/<password>')
def lol(username: str, password: str):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    if pam.authenticate(username, password):
        resp = make_response("Success")
        resp.set_cookie('username', username)
        resp.set_cookie('userhash', str(sha256(
            f"{username[:1]} + {password} + {username[1:]}".encode(
                'utf-8')).hexdigest()))
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()
        if existing_user is None:
            cursor.execute(
                'INSERT INTO users (username, userhash) VALUES (?, ?)',
                (username, str(sha256(f"{username[:1]} + {password} + {username[1:]}".encode('utf-8')).hexdigest())))
            conn.commit()
        return resp
    else:
        abort(403)


if __name__ == "__main__":
    app.run()
