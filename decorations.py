import sqlite3
import settings as s
from flask import request, redirect, make_response, flash

from functions import *


def login_required(func):
    def wrapper():
        if request.cookies.get('username') is None or request.cookies.get('userhash') is None:
            return redirect('/signin', 302)
        conn = sqlite3.connect(s.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (request.cookies.get('username'),))
        existing_user = cursor.fetchone()
        if existing_user is None:
            resp = make_response(redirect('/signin', 302))
            resp.set_cookie('username', '', expires=0)
            resp.set_cookie('userhash', '', expires=0)
            flash("You are not authorised to use this service.", "danger")
            return resp
        if existing_user[2] != request.cookies.get('userhash'):
            resp = make_response(redirect('/signin', 302))
            resp.set_cookie('username', '', expires=0)
            resp.set_cookie('userhash', '', expires=0)
            flash("You are not authorised to use this service.", "danger")
            return resp
        return func()

    wrapper.__name__ = func.__name__
    return wrapper


def login_not_required(func):
    def wrapper():
        if request.cookies.get('username') is not None and request.cookies.get('userhash') is not None:
            conn = sqlite3.connect(s.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (request.cookies.get('username'),))
            existing_user = cursor.fetchone()
            if existing_user is not None and existing_user[2] == request.cookies.get('userhash'):
                return redirect('/', 302)
        return func()

    wrapper.__name__ = func.__name__
    return wrapper


def admin_required(func):
    def wrapper():
        if not (user_in_admin_group(request.cookies.get('username'), s.admin_groups)):
            flash("You are not authorised to use this service.", "danger")
            return redirect('/', 302)
        return func()

    wrapper.__name__ = func.__name__
    return wrapper
