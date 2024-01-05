import json
import os
import pwd
from hashlib import sha256
from pwd import getpwuid

import pam
import werkzeug
from flask import Flask, render_template

from decorations import *

app = Flask(__name__)
app.secret_key = "e87d7a3c64e8fcd08c30c3404b7902e1f1f6613e114938bbd3081206f66cb179"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# if users.db doesn't exist, create it
if not os.path.isfile(s.db_path):
    open(s.db_path, 'w').close()

conn = sqlite3.connect(s.db_path)
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

@app.context_processor
def inject_user():
    if request.cookies.get('username') is None or request.cookies.get('userhash') is None:
        return dict(user={
            'is_authenticated': False,
            'username': None
        })
    conn = sqlite3.connect(s.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (request.cookies.get('username'),))
    existing_user = cursor.fetchone()
    if existing_user is None or existing_user[2] != request.cookies.get('userhash'):
        return dict(user={
            'is_authenticated': False,
            'username': None
        })
    return dict(user={
        'is_authenticated': True,
        'username': request.cookies.get('username'),
        'access': "sudo" if is_user_in_group(request.cookies.get('username'), s.admin_groups) else (
            "is_rw" if is_user_in_group(request.cookies.get('username'), s.rw_groups) else (
                "is_r" if is_user_in_group(request.cookies.get('username'), s.r_groups) else "none"))
    })

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
        conn = sqlite3.connect(s.db_path)
        cursor = conn.cursor()
        if is_password_change_required(username):
            flash("You must change your password before logging in.", "danger")
            return render_template('login.html')
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
        name: str
        description: str
        remote: str
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
    user_list = list(map(lambda i: i[0], filter(lambda i: int(i[2]) >= 1000, pwd.getpwall())))
    user_list.remove("nobody")
    user_list.insert(0, user_list.pop(user_list.index(request.cookies.get('username', ''))))
    for user in user_list:
        users.append({
            'username': user,
            'is_sudo': user_in_group(user, s.admin_groups),
            'is_rw': user_in_group(user, s.rw_groups),
            'is_r': user_in_group(user, s.r_groups)
        })
    return render_template('users.html', users=users)

@app.route('/users/create')
@login_required
@admin_required
def usercreate():
    return render_template('usercreate.html')


@app.route('/users/create/read', methods=['POST'])
@login_required
@admin_required
def read_form():
    data = request.form
    try:
        return {
            'emailId': data['userEmail'],
            'phoneNumber': data['userContact'],
            'password': data['userPassword'],
            'gender': 'Male' if data['genderMale'] else 'Female',
        }
    except werkzeug.exceptions.BadRequestKeyError:
        flash("Please fill in all the fields.", "danger")
        return redirect('/users/create', 302)


if __name__ == "__main__":
    app.run()
