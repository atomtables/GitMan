import os
import subprocess
from hashlib import sha256
import sqlite3
from flask import Flask, make_response, render_template, request, abort, redirect
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


def count_commits(repo_path):
    try:
        # Change to the repository directory
        os.chdir(repo_path)

        # Run the git command to count commits
        result = subprocess.check_output(['git', 'rev-list', '--all', '--count']).decode('utf-8').strip()

        return int(result)
    except subprocess.CalledProcessError as e:
        print(f"Error counting commits in {repo_path}: {e}")
        return 0


def login_required(func):
    def wrapper():
        if request.cookies.get('username') is None or request.cookies.get('userhash') is None:
            return redirect('/login', 403)
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (request.cookies.get('username'),))
        existing_user = cursor.fetchone()
        if existing_user is None:
            return redirect('/login', 403)
        if existing_user[2] != request.cookies.get('userhash'):
            return redirect('/login', 403)
        print("success")
        return func()
    return wrapper


@app.route('/')
@login_required
def hello_world():  # put application's code here
    # find all folders in /srv/git that end with .git
    total_commits = 0
    git_folders = [os.path.join('/srv/git', folder_name)
                   for folder_name in os.listdir('/srv/git')
                   if os.path.isdir(os.path.join('/srv/git', folder_name)) and folder_name.endswith(".git")]
    for repo_path in git_folders:
        commits = count_commits(repo_path)
        total_commits += commits
    return render_template('mainpage.html', amt_git=len(git_folders), hostname=os.uname()[1],
                           total_commits=total_commits)


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
        userhash = str(sha256(f"{username[:1]} + {password} + {username[1:]}".encode('utf-8')).hexdigest())
        resp = make_response("Success");
        resp.set_cookie('username', username)
        resp.set_cookie('userhash', userhash)
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()
        if existing_user is None:
            cursor.execute('INSERT INTO users (username, userhash) VALUES (?, ?)', (username, userhash))
            conn.commit()
        elif existing_user[2] != userhash:
            cursor.execute('UPDATE users SET userhash = ? WHERE username = ?', (userhash, username))
            conn.commit()
        return resp
    else:
        return "User: " + username + " Password: " + password + " is not valid because pam returned " + str(
            pam.authenticate(username, password))


if __name__ == "__main__":
    app.run()
