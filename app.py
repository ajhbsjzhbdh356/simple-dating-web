import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

# --- APP CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_super_secret_key_change_it_later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---

# Association table for likes
likes = db.Table('likes',
    db.Column('liker_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('liked_id', db.Integer, db.ForeignKey('user.id'))
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    bio = db.Column(db.String(500), nullable=True)
    profile_picture = db.Column(db.String(150), nullable=True, default='default.jpg')

    # Relationship for likes
    liked = db.relationship(
        'User', secondary=likes,
        primaryjoin=(likes.c.liker_id == id),
        secondaryjoin=(likes.c.liked_id == id),
        backref=db.backref('liked_by', lazy='dynamic'), lazy='dynamic'
    )

    # Methods for liking and unliking
    def like(self, user):
        if not self.has_liked(user):
            self.liked.append(user)

    def unlike(self, user):
        if self.has_liked(user):
            self.liked.remove(user)

    def has_liked(self, user):
        return self.liked.filter(likes.c.liked_id == user.id).count() > 0

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    return render_template('base.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        gender = request.form.get('gender')

        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists.')
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            gender=gender
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('profile'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('profile'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio')
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file.filename != '':
                filename = secure_filename(f"{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.profile_picture = filename

        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

@app.route('/users')
@login_required
def users():
    search_gender = request.args.get('gender', '')
    search_bio = request.args.get('bio', '')

    query = User.query.filter(User.id != current_user.id)

    if search_gender:
        query = query.filter(User.gender == search_gender)
    if search_bio:
        query = query.filter(User.bio.contains(search_bio))

    all_users = query.all()
    return render_template('users.html', users=all_users)

@app.route('/like/<int:user_id>')
@login_required
def like(user_id):
    user_to_like = User.query.get_or_404(user_id)
    current_user.like(user_to_like)
    db.session.commit()
    flash(f'You have liked {user_to_like.username}.')
    return redirect(url_for('users'))

@app.route('/matches')
@login_required
def matches():
    # Find users that the current user has liked
    liked_users = current_user.liked

    # Find users who have liked the current user
    users_who_like_me = current_user.liked_by

    # The intersection of these two groups are the matches
    my_matches = [user for user in liked_users if user in users_who_like_me]

    return render_template('matches.html', matches=my_matches)

@app.route('/messages', defaults={'recipient_id': None})
@app.route('/messages/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def messages(recipient_id):
    # If sending a message
    if request.method == 'POST':
        body = request.form.get('body')
        recipient = User.query.get_or_404(recipient_id)
        msg = Message(sender=current_user, recipient=recipient, body=body)
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent.')
        return redirect(url_for('messages', recipient_id=recipient_id))

    # Get all conversations for the current user
    sent_messages = Message.query.filter_by(sender_id=current_user.id).all()
    received_messages = Message.query.filter_by(recipient_id=current_user.id).all()

    # Get unique user IDs from all conversations
    user_ids = set()
    for msg in sent_messages:
        user_ids.add(msg.recipient_id)
    for msg in received_messages:
        user_ids.add(msg.sender_id)

    conversations = User.query.filter(User.id.in_(user_ids)).all()

    # Get conversation with a specific user if recipient_id is provided
    chat_history = []
    active_recipient = None
    if recipient_id:
        active_recipient = User.query.get_or_404(recipient_id)
        chat_history = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
            ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
        ).order_by(Message.timestamp.asc()).all()

    return render_template('messages.html', conversations=conversations, chat_history=chat_history, active_recipient=active_recipient)


# --- MAIN EXECUTION ---
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    with app.app_context():
        db.create_all()
    app.run(debug=True)