from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField
from wtforms.validators import DataRequired, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)  # Fixing Flask app initialization
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['MAIL_SERVER'] = 'smtp.yandex.ru'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'alexstudiocode@yandex.ru'
app.config['MAIL_PASSWORD'] = 'bsmuxahtgxwvonzl'
app.config['MAIL_DEFAULT_SENDER'] = 'alexstudiocode@yandex.ru'

mail = Mail(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    confirmed = db.Column(db.Boolean, default=False)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='На рассмотрении')
    admin_response = db.Column(db.Text, nullable=True)

class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=2, max=20)])
    email = EmailField('Электронная почта', validators=[DataRequired()])
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_username = User.query.filter_by(username=form.username.data).first()
        existing_email = User.query.filter_by(email=form.email.data).first()
        
        if existing_username:
            flash('Такое имя пользователя уже занято. Пожалуйста, выберите другое имя.', 'danger')
            return redirect(url_for('register'))

        if existing_email:
            flash('Такой адрес электронной почты уже зарегистрирован. Пожалуйста, используйте другой адрес.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        # Email confirmation process
        token = s.dumps(new_user.email, salt='email-confirm')
        confirm_url = url_for('confirm_email', token=token, _external=True)

        msg = Message('Подтверждение регистрации',
                      sender='AlexStudio Code <alexstudiocode@yandex.ru>',
                      recipients=[new_user.email])
        msg.html = f"""
                <!DOCTYPE html>
                <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Подтверждение регистрации</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            background-color: #f7f7f7;
                            margin: 0;
                            padding: 20px;
                        }}
                        .container {{
                            background-color: #fff;
                            padding: 20px;
                            border-radius: 5px;
                            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                        }}
                        h1 {{
                            color: #333;
                        }}
                        a {{
                            color: #007BFF;
                            text-decoration: none;
                            font-weight: bold;
                        }}
                        .footer {{
                            margin-top: 20px;
                            font-size: 0.8em;
                            color: #777;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Подтверждение регистрации</h1>
                        <p>Здравствуйте, {new_user.username}!</p>
                        <p>Чтобы подтвердить регистрацию, пожалуйста, перейдите по следующей ссылке:</p>
                        <p><a href="{confirm_url}">Подтвердить регистрацию</a></p>
                        <p>С уважением,<br>Команда AlexStudio Code.</p>
                        <div class="footer">
                            <p>Если у вас возникли вопросы, свяжитесь с нашей службой поддержки.</p>
                        </div>
                    </div>
                </body>
                </html>
                """
        mail.send(msg)

        flash('Пожалуйста, проверьте ваш email для подтверждения регистрации. Если не пришел код, пожалуйста, свяжитесь с нашей технической поддержкой.', 'info')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/confirm_email/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)  # check token
        user = User.query.filter_by(email=email).first()
        if user and not user.confirmed:
            user.confirmed = True
            db.session.commit()
            flash('Ваш email успешно подтвержден!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Ваш email уже подтвержден или не найден.', 'info')
            return redirect(url_for('login'))
    except Exception as e:
        flash('Токен недействительный или истек.', 'danger')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            if user.confirmed:
                flash('Вы успешно вошли в систему!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Пожалуйста, подтвердите ваш email перед входом.', 'warning')
        else:
            flash('Неправильное имя пользователя или пароль.', 'danger')

    return render_template('login.html', form=form, user=current_user)

@app.route('/logout', methods=['POST'])
@login_required  # Это гарантирует, что только аутентифицированные пользователи могут выйти
def logout():
    logout_user()  # Функция для выхода пользователя
    return redirect(url_for('home'))  # Перенаправление на главную страницу после выхода

@app.route('/teh_help')
def application():
    applications = Application.query.all()
    return render_template('application.html', applications=applications)

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    description = request.form['description']

    new_application = Application(name=name, description=description)  # Added user_id
    db.session.add(new_application)
    db.session.commit()

    return redirect(url_for('home'))

@app.route('/admin')
@login_required
def admin():
    if current_user.username not in ['Alex-Admin', 'Bismark-Admin']:
        return "У вас нет разрешения на доступ к этой странице! Чтобы вернуться нажмите стрелку назад в браузере."

    return render_template('admin.html')


@app.route('/admin_teh')
@login_required
def adminteh():
    if current_user.username not in ['Alex-Admin', 'Bismark-Admin']:
        return "У вас нет разрешения на доступ к этой странице! Чтобы вернуться нажмите стрелку назад в браузере."

    applications = Application.query.all()
    return render_template('admin-teh.html', applications=applications)


@app.route('/teh_help/<int:id>')
def view_application(id):
    application = Application.query.get_or_404(id)
    return render_template('view_application.html', application=application)

@app.route('/respond/<int:id>', methods=['POST'])
def respond(id):
    application = Application.query.get_or_404(id)
    response = request.form['response']
    
    # Сохраняем ответ админа в базе данных
    application.admin_response = response
    db.session.commit()

    return redirect(url_for('adminteh'))

@app.route('/mark_as_reviewed/<int:id>')
def mark_as_reviewed(id):
    application = Application.query.get_or_404(id)
    application.status = 'Одобрено'
    db.session.commit()
    return redirect(url_for('adminteh'))

@app.route('/mark_as_rejected/<int:id>')  # Renamed for clarity
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
        db.create_all()  # Creating the database and tables at first run
    app.run(debug=True, port=8080)