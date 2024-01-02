import datetime
import grp
import json
import os
import pwd
import sqlite3
import subprocess
from hashlib import sha256
from pwd import getpwuid

import git

import pam
import psutil
from flask import Flask, make_response, render_template, request, redirect, flash
from git import Repo

app = Flask(__name__)
app.secret_key = "yowhatsgoodmyboy"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "users.db")

# if users.db doesn't exist, create it
if not os.path.isfile(db_path):
    open(db_path, 'w').close()

conn = sqlite3.connect(db_path); cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        userhash TEXT NOT NULL
    )''')

conn.commit(); cursor.close(); conn.close()


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


def is_git_repo(path):
    try:
        _ = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError:
        return False


def get_last_commit_time(repo_path):
    try:
        repo = Repo(repo_path)
        last_commit = next(repo.iter_commits())
        return last_commit.committed_datetime
    except Exception as e:
        # TypeError: can't compare offset-naive and offset-aware datetimes
        return datetime.datetime(1970, 1, 1, 0, 0, 0, 0, datetime.timezone.utc)


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


def is_user_in_group(username, group):
    try:
        result = subprocess.run(['id', '-nG', username], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                check=True)
        groups = result.stdout.strip().split()
        return group in groups
    except subprocess.CalledProcessError as e:
        return False


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


def login_not_required(func):
    def wrapper():
        if request.cookies.get('username') is not None and request.cookies.get('userhash') is not None:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (request.cookies.get('username'),))
            existing_user = cursor.fetchone()
            if existing_user is not None and existing_user[2] == request.cookies.get('userhash'):
                return redirect('/', 302)
        return func()

    wrapper.__name__ = func.__name__
    return wrapper


@app.route('/')
def mainpage():
    total_commits = 0
    git_folders = [os.path.join('/srv/git', folder_name)
                   for folder_name in os.listdir('/srv/git')
                   if is_git_repo(os.path.join('/srv/git', folder_name))]
    for repo_path in git_folders:
        commits = count_commits(repo_path)
        total_commits += commits
    return render_template('mainpage.html', amt_git=len(git_folders), hostname=os.uname()[1],
                           total_commits=total_commits)


@app.route('/signin', methods=['GET', 'POST'])
@login_not_required
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        if pam.authenticate(username, password):
            if not (is_user_in_group(username, 'wheel') or
                    is_user_in_group(username, 'sudo') or
                    is_user_in_group(username, 'gitman')):
                flash("You are not authorised to use this service.", "danger")
            else:
                flash(f"Successfully logged in as {username}", "success")
                userhash = str(sha256(f"{username[:1]} + {password} + {username[1:]}".encode('utf-8')).hexdigest())
                resp = redirect('/')
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
    resp = make_response(redirect('/'))
    resp.set_cookie('username', '', expires=0)
    resp.set_cookie('userhash', '', expires=0)
    return resp


@app.route('/repositories')
@login_required
def repositories():
    git_folders = [os.path.join('/srv/git', folder_name)
                   for folder_name in os.listdir('/srv/git')
                   if os.path.isdir(os.path.join('/srv/git', folder_name)) and folder_name.endswith(".git")]
    git_folders = sorted(git_folders, key=get_last_commit_time, reverse=True)
    print(git_folders)
    repositories = []
    for folder in git_folders:
        name: str; description: str; remote: str
        gitinfo_path = os.path.join(folder, "gitinfo")
        if os.path.isfile(gitinfo_path):
            try:
                with open(gitinfo_path, 'r') as f:
                    gitinfo = json.loads(f.read().strip())
                    name = gitinfo.get('name', folder.split('/')[-1].split('.')[0])
                    description = gitinfo.get('description', '')
                    # get the creator of the folder. this will either be in gitinfo or the owner of the folder
                    creator = gitinfo.get('creator', getpwuid(os.stat(folder).st_uid).pw_name)
            except json.decoder.JSONDecodeError:
                name = folder.split('/')[-1].split('.')[0]
                description = ''
                creator = getpwuid(os.stat(folder).st_uid).pw_name
        else:
            name = folder.split('/')[-1].split('.')[0]
            description = ''
            creator = getpwuid(os.stat(folder).st_uid).pw_name
        remote = f"{request.cookies.get('username')}@{os.uname()[1]}:{folder}"
        repositories.append({
            'name': name,
            'description': description,
            'commits': count_commits(folder),
            'remote': remote,
            'creator': creator
        })

    return render_template('repositories.html', repositories=repositories)


@app.route('/users')
@login_required
def userlist():
    users = []
    user_list = list(map(lambda i: i[0], filter(lambda i: int(i[2]) >= 1000, pwd.getpwall()))).remove("nobody")
    for user in user_list:
        users.append({
            'username': user,
            'is_sudo': is_user_in_group(user, 'sudo'),
            'is_wheel': is_user_in_group(user, 'wheel'),
            'is_gitman': is_user_in_group(user, 'gitman'),
            'is_admin': is_user_in_group(user, 'admin'),
            'is_active': True if user in user_list else False
        })
    return render_template('users.html', users=users)


if __name__ == "__main__":
    app.run()
