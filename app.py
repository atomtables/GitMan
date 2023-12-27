import os
import subprocess
from hashlib import sha256
import sqlite3
from flask import Flask, make_response, render_template, request, abort, redirect, flash
import pam

app = Flask(__name__)
app.secret_key = "yowhatsgoodmyboy"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "users.db")

# if users.db doesn't exist, create it
if not os.path.isfile(db_path):
    open(db_path, 'w').close()

conn = sqlite3.connect(db_path)
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


# context processor that passes if user is logged in and username through a users.___ dictionary
@app.context_processor
def inject_user():
    if request.cookies.get('username') is None or request.cookies.get('userhash') is None:
        return dict(user={
            'is_authenticated': False,
            'username': None
        })
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (request.cookies.get('username'),))
    existing_user = cursor.fetchone()
    if existing_user is None:
        return dict(user={
            'is_authenticated': False,
            'username': None
        })
    if existing_user[2] != request.cookies.get('userhash'):
        return dict(user={
            'is_authenticated': False,
            'username': None
        })
    return dict(user={
        'is_authenticated': True,
        'username': request.cookies.get('username')
    })


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
            return redirect('/signin', 302)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (request.cookies.get('username'),))
        existing_user = cursor.fetchone()
        if existing_user is None:
            return redirect('/signin', 302)
        if existing_user[2] != request.cookies.get('userhash'):
            return redirect('/signin', 302)
        return func()

    wrapper.__name__ = func.__name__
    return wrapper


@app.route('/')
def mainpage():
    total_commits = 0
    git_folders = [os.path.join('/srv/git', folder_name)
                   for folder_name in os.listdir('/srv/git')
                   if os.path.isdir(os.path.join('/srv/git', folder_name)) and folder_name.endswith(".git")]
    for repo_path in git_folders:
        commits = count_commits(repo_path)
        total_commits += commits
    return render_template('mainpage.html', amt_git=len(git_folders), hostname=os.uname()[1],
                           total_commits=total_commits)


@app.route('/signin', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        if pam.authenticate(username, password):
            flash(f"Successfully logged in as {username}", "success")
            userhash = str(sha256(f"{username[:1]} + {password} + {username[1:]}".encode('utf-8')).hexdigest())
            resp = make_response("Success")
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
            cursor.close()
            conn.close()
            return resp
        else:
            flash(f"Invalid username/password combination. (Hint: use your authorised linux credentials)", "danger")

    return render_template('login.html')


@app.route('/signout')
@login_required
def logout():
    resp = make_response(redirect('/signin'))
    resp.set_cookie('username', '', expires=0)
    resp.set_cookie('userhash', '', expires=0)
    return resp


@app.route('/authenticate/<username>/<password>')
def authenticate(username: str, password: str):
    conn = sqlite3.connect(db_path)
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
        cursor.close()
        conn.close()
        return resp
    else:
        return "User: " + username + " Password: " + password + " is not valid because pam returned " + str(
            pam.authenticate(username, password))


if __name__ == "__main__":
    app.run()
