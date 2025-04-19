# -- coding: utf-8 --
from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField
from wtforms.validators import DataRequired, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)  # Инициализация Flask
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads/'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Добавлено поле user_id
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='На рассмотрении')
    admin_response = db.Column(db.Text, nullable=True)  # Новое поле для ответа админа



    # Связь с моделью User
    user = db.relationship('User', backref='applications')


class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired()])  # тут всё с отступом внутри класса
    password = PasswordField('Пароль', validators=[DataRequired()])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Неправильное имя пользователя или пароль.', 'danger')
    return render_template('login.html', form=form, user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Такое имя пользователя уже занято.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Вы успешно зарегистрированы! Теперь можете войти.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.errorhandler(404)
def error404(error):
    return render_template('404.html')

@app.route('/forma_p')
def forma_p():
    return render_template('forma-pod.html')

@app.route('/game')
def game():
    return render_template('game.html')

@app.route('/teh_help')
@login_required
def application():
    applications = Application.query.all()
    return render_template('application.html', applications=applications)

@app.route('/obrabotka_personalnih_dannih')
def obr():
    return render_template("obr.html")


@app.route('/submit', methods=['POST'])
@login_required
def submit():
    description = request.form['description']

    new_application = Application(user_id=current_user.id, description=description)  # Добавлено user_id
    db.session.add(new_application)
    db.session.commit()

    return redirect(url_for('home'))

@app.route('/admin')
@login_required
def admin():
    if current_user.username not in ['Alex-Admin', 'Bismark-Admin']:
        return "У вас нет доступа к этой странице!"
    return render_template('admin.html')

@app.route('/admin_teh')
@login_required
def adminteh():
    if current_user.username not in ['Alex-Admin', 'Bismark-Admin']:
        return "У вас нет доступа к этой странице!"
    applications = Application.query.all()
    return render_template('admin-teh.html', applications=applications)

@app.route('/teh_help/<int:id>')
@login_required
def view_application(id):
    application = Application.query.get_or_404(id)
    return render_template('view_application.html', application=application)

@app.route('/respond/<int:id>', methods=['POST'])
@login_required
def respond(id):
    application = Application.query.get_or_404(id)
    response = request.form['response']
    application.admin_response = response
    db.session.commit()
    return redirect(url_for('adminteh'))

@app.route('/mark_as_reviewed/<int:id>')
@login_required
def mark_as_reviewed(id):
    application = Application.query.get_or_404(id)
    application.status = 'Одобрено'
    db.session.commit()
    return redirect(url_for('adminteh'))

@app.route('/mark_as_rejected/<int:id>')
@login_required
def mark_as_rejected(id):
    application = Application.query.get_or_404(id)
    application.status = 'Отказано'
    db.session.commit()
    return redirect(url_for('adminteh'))

@app.route('/articles/<int:page>')
def articles(page=1):
    articles_list = fetch_articles(page)
    max_pages = (len(articles_list) + 5) // 6
    return render_template('articles.html', articles=articles_list, page=page, max_pages=max_pages)

def fetch_articles(page=1):
    url = f'https://new-science.ru/page/{page}/?s=%D0%B3%D0%BB%D0%BE%D0%B1%D0%B0%D0%BB%D1%8C%D0%BD%D0%BE%D0%B5+%D0%BF%D0%BE%D1%82%D0%B5%D0%BF%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5'
    articles = []
    response = requests.get(url)
    bs = BeautifulSoup(response.text, "lxml")
    temp = bs.find_all('div', 'post-details')
    for post in temp:
        title = post.find('h2', 'post-title').text.strip() if post.find('h2', class_='post-title') else "No Title"
        link = post.find('h2', 'post-title').find('a')['href'] if post.find('h2', class_='post-title') else "No Link"
        views = post.find('span', 'meta-views meta-item').text.strip() if post.find('span', 'meta-views meta-item') else "No Views"
        date = post.find('span', 'date meta-item tie-icon').text.strip() if post.find('span', 'date meta-item tie-icon') else "No Date"
        thumb_tag = post.find_previous('a', class_='post-thumb')
        image = None
        if thumb_tag:
            picture_tag = thumb_tag.find('picture')
            if picture_tag:
                source_tag = picture_tag.find('source')
                if source_tag and 'srcset' in source_tag.attrs:
                    srcset_value = source_tag['srcset']
                    image = srcset_value.split(',')[0].split()[0] if ',' in srcset_value else srcset_value.split()[0]
        articles.append({
            'title': title,
            'link': link,
            'views': views,
            'date': date,
            'image': image if image else "No Image"
        })
    return articles

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаем таблицы
    app.run(debug=True, host='0.0.0.0')