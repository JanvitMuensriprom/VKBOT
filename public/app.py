import vk_api
from flask import Flask, request, render_template, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from datetime import datetime, date, timedelta
from flask_migrate import Migrate
import os
import requests
from collections import defaultdict
from datetime import datetime, timedelta

vk_session = vk_api.VkApi(token='2a3d72c72a3d72c72a3d72c7b1292f81eb22a3d2a3d72c74e38a51a1737368d2c80af10')
vk = vk_session.get_api()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users5.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(20), nullable=False)
    last_login = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Group:
    def __init__(self, name, description, status, visibility, link, image, user_id):
        self.name = name
        self.description = description
        self.status = status
        self.visibility = visibility
        self.link = link
        self.image = image
        self.user_id = user_id

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        # Get the form data
        username = request.form['username']
        password = request.form['password']

        # Create a new User object
        new_user = User(username=username, password=password)

        # Add the user to the database
        with app.app_context():
            db.session.add(new_user)
            db.session.commit()

            # Log the user in
            session['user_id'] = new_user.id

        # Redirect the user to the dashboard
        return redirect(url_for('dashboard'))

    # If the request method is GET, render the create account page
    return render_template('create_account.html')

class VkAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('vk_accounts', lazy=True))
    status = db.Column(db.String(20), nullable=False, default='Active')
    total_reposts = db.Column(db.Integer, nullable=False, default=0)
    today_reposts = db.Column(db.Integer, nullable=False, default=0)
    last_post_date = db.Column(db.Date)

    def update_status(self):
    # Authenticate with VK using the VK account's username and password from the database
        vk_session = vk_api.VkApi(self.username, self.password)
        vk_session.auth()

        # Get the API object
        vk = vk_session.get_api()

        # Check if the account is banned or temporarily banned
        try:
            account_info = vk.account.getInfo()
        except vk_api.exceptions.ApiError as e:
            if e.code == 5:
                # Invalid login or password
                self.status = 'Invalid'
            elif e.code == 18:
                # User is banned
                self.status = 'Ban'
            elif e.code == 19:
                # User is temporarily banned
                self.status = 'Temporary Ban'
            elif e.code == 14:
                # Captcha is required
                captcha_key = input('Enter the captcha: ')
                vk_session.method('captcha.force', {'captcha_key': captcha_key, 'captcha_sid': e.captcha_sid})
                # Retry the request
                account_info = vk.account.getInfo()
            else:
                # Other error
                self.status = 'Unknown Error'
        else:
            # Account is active
            self.status = 'Active'

        # Commit the changes to the database
        with app.app_context():
            db.session.commit()

# check if User and VkAccount tables exist in the database and create them if they don't
with app.app_context():
    if not inspect(db.engine).has_table('user'):
        db.create_all()
    if not inspect(db.engine).has_table('vk_account'):
        db.create_all()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the form data
        username = request.form['username']
        password = request.form['password']

        # Check if the user exists in the database
        user = User.query.filter_by(username=username, password=password).first()
        if user is None:
            return render_template('login.html', error='Invalid username or password.')
        flash('Invalid login or password.')

        # Update the user's last login time in the database
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Store the user's ID in the session
        session['user_id'] = user.id

        # Redirect to the dashboard
        return redirect(url_for('dashboard'))

    # If the request method is GET, render the login page
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the user's ID from the session
    session.pop('user_id', None)

    # Redirect to the login page
    return redirect(url_for('login'))
########################################## DashBoard Section ###########################
@app.route('/dashboard')
def dashboard():
    # Check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the user from the database using their ID
    user_id = session['user_id']
    with app.app_context():
        user = User.query.get(user_id)
        vk_accounts = VkAccount.query.filter_by(user_id=user_id).all()

        # Iterate over all the VK accounts and get the post count for each account
        for vk_account in vk_accounts:
            vk_session = vk_api.VkApi(vk_account.username, vk_account.password)
            vk_session.auth()
            vk = vk_session.get_api()
            post_count = vk.wall.get()['count']
            vk_account.total_posts = post_count
            db.session.commit()

        db.session.add(user)

    # Render the dashboard page with the VK accounts
    return render_template('dashboard.html', user=user, vk_accounts=vk_accounts)

@app.route('/add_vk_account', methods=['GET', 'POST'])
def add_vk_account():
    # Check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the user from the database using their ID
    user_id = session['user_id']
    user = User.query.get(user_id)

    if request.method == 'POST':
        # Get the form data
        username = request.form['username']
        password = request.form['password']

        # Authenticate with VK using the VK account's username and password
        vk_session = vk_api.VkApi(username, password)
        try:
            vk_session.auth()
        except vk_api.exceptions.BadPassword:
            flash('Invalid username or password. Please try again.', 'error')
            return redirect(url_for('add_vk_account'))
        except vk_api.exceptions.Captcha as e:
            flash('Captcha required. Please try again later.', 'error')
            return redirect(url_for('add_vk_account'))
        except vk_api.exceptions.AuthError:
            flash('Invalid username or password. Please try again.', 'error')
            return redirect(url_for('add_vk_account'))
        except vk_api.exceptions.ApiError as e:
            if e.code == 18:
                flash('This account has been banned. Please use another account.', 'error')
                return redirect(url_for('add_vk_account'))
            elif e.code == 19:
                flash('This account has been temporarily banned. Please use another account.', 'error')
                return redirect(url_for('add_vk_account'))
            else:
                flash('An unknown error occurred. Please try again.', 'error')
                return redirect(url_for('add_vk_account'))

        # Check if the account is a VK account
        try:
            vk = vk_session.get_api()
            account_info = vk.account.getInfo()
        except vk_api.exceptions.ApiError as e:
            if e.code == 5:
                flash('Invalid username or password. Please try again.', 'error')
            else:
                flash('An unknown error occurred. Please try again.', 'error')
            return redirect(url_for('add_vk_account'))

        # Create a new VkAccount object
        vk_account = VkAccount(username=username, password=password, user_id=user.id)

        # Add the VK account to the database
        db.session.add(vk_account)
        db.session.commit()

        # Redirect to the dashboard
        return redirect(url_for('dashboard'))

    # If the request method is GET, render the add VK account page
    return render_template('add_vk_account.html', user=user)

@app.route('/vk_account/<int:vk_account_id>/repost-history')
def vk_account_repost_history(vk_account_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the user from the database using their ID
    with app.app_context():
        user = User.query.filter_by(id=session['user_id']).first()
        
        # Get the VK account from the database using its ID
        vk_account = VkAccount.query.filter_by(id=vk_account_id, user_id=user.id).first()

        # If the VK account doesn't exist or is associated with another user, render an error message
        if vk_account is None:
            return render_template('vk_account_repost_history.html', error='VK account not found.')

        # Get all the reposts for the VK account from the database
        with app.app_context():
            reposts = Repost.query.filter_by(vk_account_id=vk_account_id).all()

    # Render the VK account repost history page with the repost data
    return render_template('vk_account_repost_history.html', vk_account=vk_account, reposts=reposts)

class Repost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vk_account_id = db.Column(db.Integer, db.ForeignKey('vk_account.id'), nullable=False)
    group_name = db.Column(db.String(50), nullable=False)
    post_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(200))
    repost_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    image = db.Column(db.LargeBinary)

with app.app_context():
    if not inspect(db.engine).has_table('repost'):
        db.create_all()

@app.route('/vk_account/<int:vk_account_id>/repost', methods=['POST'])
def vk_account_repost(vk_account_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the user from the database using their ID
    with app.app_context():
        user = User.query.filter_by(id=session['user_id']).first()
        
        # Get the VK account from the database using its ID
        vk_account = VkAccount.query.filter_by(id=vk_account_id, user_id=user.id).first()

        # If the VK account doesn't exist or is associated with another user, render an error message
        if vk_account is None:
            return render_template('vk_account_repost.html', error='VK account not found.')

        # Authenticate with VK using the VK account's username and password from the database
        vk_session = vk_api.VkApi(vk_account.username, vk_account.password)
        vk_session.auth()

        # Get the API object
        vk = vk_session.get_api()

        # Get the form data
        group_name = request.form['group_name']
        message = request.form['message']
        repost = request.form.get('repost')
        comment = request.form.get('comment')
        like = request.form.get('like')

        # Get the numeric ID of the group
        group_info = vk.utils.resolveScreenName(screen_name=group_name)
        group_id = -group_info['object_id']

        # Get the latest post from the group
        posts = vk.wall.get(owner_id=group_id, count=1)['items']
        if len(posts) == 0:
            return render_template('vk_account_repost.html', error=f'There are no posts in group {group_name}.')
        latest_post = posts[0]
        if not isinstance(latest_post, dict):
            return render_template('vk_account_repost.html', error=f'The latest post in group {group_name} is not a dictionary: {latest_post}')

        # Check if the post has already been reposted
        post_id = latest_post['id']
        if Repost.query.filter_by(vk_account_id=vk_account.id, post_id=post_id).first() is not None:
            return render_template('vk_account_repost.html', error=f'This post has already been reposted.')

        # Check if too many posts have been reposted from the group today
        today = date.today()
        group_reposts = defaultdict(int)
        for repost in Repost.query.filter_by(vk_account_id=vk_account.id):
            if repost.repost_date.date() == today:
                group_reposts[repost.group_name] += 1
        if group_name in group_reposts and group_reposts[group_name] >= 3:
            return render_template('vk_account_repost.html', error=f'Too many posts from {group_name} have already been reposted today.')

        # Construct the attachment object
        attachment = f'wall{group_id}_{post_id}'

    # Repost the post
    try:
        if repost == 'on':
            vk.wall.repost(object=attachment, message=message, group_id=vk_account.group_id)
        else:
            vk.wall.repost(object=attachment, message=message)
    except vk_api.exceptions.ApiError as e:
        return render_template('vk_account_repost.html', error=f'Error reposting: {e}')

    # If the user chose to comment, post a comment on the repost
    if comment == 'on':
        try:
            vk.wall.createComment(owner_id=vk_account.group_id, post_id=post_id, message=message)
        except vk_api.exceptions.ApiError as e:
            return render_template('vk_account_repost.html', error=f'Error commenting: {e}')

    # If the user chose to like, like the repost
    if like == 'on':
        try:
            vk.likes.add(type='post', owner_id=vk_account.group_id, item_id=post_id)
        except vk_api.exceptions.ApiError as e:
            return render_template('vk_account_repost.html', error=f'Error liking: {e}')

    # Save the repost to the database
    with app.app_context():
        repost = Repost(vk_account_id=vk_account.id, group_name=group_name, post_id=post_id, repost_date=datetime.now())
        db.session.add(repost)
        db.session.commit()

    # Redirect to the VK account page
    return redirect(url_for('vk_account', vk_account_id=vk_account_id))
if __name__ == '__main__':
    app.run('0.0.0.0')