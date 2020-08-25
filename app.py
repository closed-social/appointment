from flask import Flask, request, session, render_template, send_from_directory, abort, redirect
from flask_sqlalchemy import SQLAlchemy
from mastodon import Mastodon
import re, random, string, os, hashlib

CLIENT_ID = 'mYh-LeEJwrSUk2r4aSEXhTtO3g6bS8jO-Zfw9ZETY0U'
CLIENT_SEC = open('client.secret', 'r').read().strip()
API_BASE_URL = 'https://thu.closed.social'

WORK_URL = 'https://closed.social'
WORK_URL = 'http://127.0.0.1:5000'

REDIRECT_URI = WORK_URL + '/appointment/auth'

LOGIN_URL = Mastodon(api_base_url=API_BASE_URL) \
                .auth_request_url(
                    client_id = CLIENT_ID,
                    redirect_uris = REDIRECT_URI,
                    scopes = ['read:accounts']
                )

app = Flask(__name__)
app.config['SECRET_KEY'] = open('client.secret', 'r').read().strip()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ask.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_AS_ASCII'] = False

db = SQLAlchemy(app)

us = db.Table('us',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('activity_id', db.Integer, db.ForeignKey('activity.id'), primary_key=True)
)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    name = db.Column(db.String(16))
    desc = db.Column(db.String(64))
    pars = db.relationship('User', secondary=us, lazy='subquery',
        backref=db.backref('activities', lazy=True))

    def __init__(self, date):
        self.date = date

    def __repr__(self):
        return f"@{self.name}[{self.desc}](self.date)"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    acct = db.Column(db.String(64))
    disp = db.Column(db.String(64))
    avat = db.Column(db.String(256))
    url  = db.Column(db.String(128))

    def __init__(self, acct):
        self.acct = acct

    def __repr__(self):
        return f"@{self.acct}[{self.disp}]"

@app.route('/img/<path:path>')
def send_img(path):
    return send_from_directory('static/img', path)

@app.route('/appointment/footer.html')
def root_footer():
    return app.send_static_file('footer.html')

@app.route('/appointment/')
def home():
    acct = session.get('user')
    if not acct:
        return redirect(LOGIN_URL)

    print(session)
    u = User.query.filter_by(acct=acct).first()
    if not u:
        return redirect('logout')

    return render_template('list.html', u=u)

@app.route('/appointment/auth')
def log_in():
    code = request.args.get('code')
    client = Mastodon(client_id = CLIENT_ID, client_secret = CLIENT_SEC, api_base_url = API_BASE_URL)
    token = client.log_in(code=code, redirect_uri=REDIRECT_URI, scopes=['read:accounts'])
    info = client.account_verify_credentials()

    session['user'] = info.acct
    session.permanent = True

    u = User.query.filter_by(acct=info.acct).first()
    if not u:
        u = User(info.acct)
        db.session.add(u)
    
    u.disp = info.display_name
    u.avat = info.avatar
    u.url  = info.url
    
    db.session.commit()

    return redirect('.') 

@app.route('/appointment/logout')
def log_out():
    session.pop('user')
    return redirect('.')

if __name__ == '__main__':
    app.run(debug=True)

