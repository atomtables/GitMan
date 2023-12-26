from hashlib import sha256

from flask import Flask, make_response, render_template
import pam

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return '<h1>Hello World!</h1> <p>average yeet enjoyer</p>'


@app.route('/authenticate/<username>/<password>')
def lol(username: str, password: str):
    if pam.authenticate(username, password):
        resp = make_response("render_template()")
        resp.set_cookie('username', username)
        resp.set_cookie('userhash', str(sha256(f"username[:1] + password + username[1:]".encode('utf-8')).hexdigest()))
        return resp
    else:
        return "Fail"


if __name__ == "__main__":
    app.run()
