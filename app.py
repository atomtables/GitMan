from flask import Flask
import pam

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return '<h1>Hello World!</h1> <p>average yeet enjoyer</p>'


@app.route('/authenticate/<username>/<password>')
def lol(username: str, password: str):
    pam.authenticate(username, password)


if __name__ == "__main__":
    app.run()
