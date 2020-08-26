from flask import Flask, request, session, render_template, send_from_directory, abort, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login  import LoginManager, login_user, logout_user, login_required, current_user
from mastodon import Mastodon
import re, random, string, os, hashlib
from datetime import datetime, date

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

login_manager = LoginManager()
login_manager.init_app(app)

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

    def __init__(self, name, desc, date):
        self.name = name
        self.desc = desc
        self.date = date

    def __repr__(self):
        return f"{self.name}[{self.desc}](self.date)"

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

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.acct

@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(acct=user_id).first()

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(LOGIN_URL)

@app.route('/img/<path:path>')
def send_img(path):
    return send_from_directory('static/img', path)

@app.route('/appointment/footer.html')
def root_footer():
    return app.send_static_file('footer.html')

@app.route('/appointment/')
@login_required
def home():
    if 'all' in request.args:
        aq = Activity.query
    else:
        aq = Activity.query.filter(Activity.date >= date.today())
    
    return render_template('list.html', u=current_user, a=aq.order_by(Activity.date).all())

@app.route('/appointment/auth')
def auth():
    code = request.args.get('code')
    client = Mastodon(client_id = CLIENT_ID, client_secret = CLIENT_SEC, api_base_url = API_BASE_URL)
    token = client.log_in(code=code, redirect_uri=REDIRECT_URI, scopes=['read:accounts'])
    info = client.account_verify_credentials()

    u = User.query.filter_by(acct=info.acct).first()
    if not u:
        u = User(info.acct)
        db.session.add(u)
    
    u.disp = info.display_name
    u.avat = info.avatar
    u.url  = info.url
    
    db.session.commit()

    login_user(u, remember=True)

    return redirect('.') 

@app.route('/appointment/logout')
@login_required
def logout():
    logout_user()
    return redirect('.')

@app.route('/appointment/new', methods=['POST'])
@login_required
def new():
    name = request.form.get('name')
    date = datetime.strptime(request.form.get('date'), "%Y-%m-%d").date()

    desc = request.form.get('desc') or ''
    print(name, date, desc)
    if not name or not date or len(name)>16 or len(desc)>64:
        abort(422)

    act = Activity(name, desc, date)
    act.pars = [current_user]
    db.session.add(act)
    db.session.commit()

    return redirect(f"{act.id}/{hashlib.md5(act.name.encode('utf-8')).hexdigest()[0:7]}")

@app.route('/appointment/<int:aid>/<md5>')
def detail(aid, md5):
    act = Activity.query.get(aid)
    if not act or md5 != hashlib.md5(act.name.encode("utf-8")).hexdigest()[0:7]:
        abort(404)

    return render_template('detail.html', act=act, joined=(current_user and current_user in act.pars))

@app.route('/appointment/<int:aid>/join', methods=['POST'])
@login_required
def join(aid):
    act = Activity.query.get(aid)
    if not act:
        abort(404)
    
    if current_user not in act.pars:
        act.pars.append(current_user)
        db.session.commit()
    
    return redirect(hashlib.md5(act.name.encode("utf-8")).hexdigest()[0:7])

@app.route('/appointment/<int:aid>/left', methods=['POST'])
@login_required
def left(aid):
    act = Activity.query.get(aid)
    if not act:
        abort(404)
    
    if current_user in act.pars:
        act.pars.remove(current_user)
        if not act.pars:
            db.session.delete(act)
        db.session.commit()
    
    return redirect('..')
    

if __name__ == '__main__':
    app.run(debug=True)

