from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
import re
import secrets
import string
import os
import uuid

from models import db, User, Announcement, Post, Comment, generate_anonymous_username, BannedRegistration

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

# 数据库配置：Render 用 PostgreSQL，本地开发用 SQLite
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
else:
    database_url = 'sqlite:///forum.db'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}
# ========== 文件上传配置 ==========
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'txt', 'zip', 'rar', 'doc', 'docx', 'xls', 'xlsx'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ========== 敏感词列表 ==========
SENSITIVE_WORDS = [
    '操', '草', '日', '妈', '逼', '屌', '傻逼', '混蛋', '他妈的', '艹逼', '傻子', '白痴', '废物', 'cnm', 'lg', 'disrimination', '死妈',
    'fuck', 'shit', 'bitch', 'sex', '色情', '情色', '约炮', '一夜情', '裸照', '黄片', '草泥马', '操你妈'
]

def check_sensitive_words(text):
    text_lower = text.lower()
    for word in SENSITIVE_WORDS:
        if word.lower() in text_lower:
            return True, word
    return False, None

# ========== 版块列表 ==========
SECTIONS = {
    'confession': '💕 表白墙',
    'news': '📰 校园新闻',
    'academic': '📚 学术讨论',
    'general': '💬 综合讨论'
}

# ========== 管理员权限装饰器 ==========
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('需要管理员权限', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ========== 学号验证 ==========
def validate_student_id(student_id):
    valid_prefixes = ['26', '27', '28', '29', '30', '31']
    pattern = r'^(26|27|28|29|30|31)[a-z]+$'
    if not re.match(pattern, student_id):
        return False
    prefix = student_id[:2]
    return prefix in valid_prefixes

# ========== 检查学号是否被禁止注册 ==========
def is_student_id_banned(student_id):
    now = datetime.now()
    record = BannedRegistration.query.filter(
        BannedRegistration.student_id == student_id,
        BannedRegistration.banned_until > now
    ).first()
    if record:
        days_left = (record.banned_until - now).days
        if (record.banned_until - now).seconds > 0 and days_left == 0:
            days_left = 1
        return True, days_left
    return False, 0

# ========== 文件上传辅助函数 ==========
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== 路由 ==========
@app.route('/')
def index():
    announcements = Announcement.query.order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc()
    ).all()

    latest_posts = {}
    for section_key in SECTIONS.keys():
        query = Post.query.filter_by(section=section_key)
        if section_key == 'confession':
            query = query.filter_by(is_approved=True)
        latest_posts[section_key] = query.order_by(Post.created_at.desc()).limit(5).all()
    return render_template('index.html',
                           sections=SECTIONS,
                           latest_posts=latest_posts,
                           announcements=announcements)

@app.route('/section/<section_name>')
def view_section(section_name):
    if section_name not in SECTIONS:
        return '版块不存在', 404
    query = Post.query.filter_by(section=section_name)
    if section_name == 'confession':
        query = query.filter_by(is_approved=True)
    posts = query.order_by(Post.created_at.desc()).limit(20).all()
    return render_template('section.html',
                         section_name=section_name,
                         section_title=SECTIONS[section_name],
                         posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        account_type = request.form.get('account_type')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        student_id = request.form.get('student_id')

        if account_type not in ['real', 'anonymous']:
            flash('请选择账号类型', 'danger')
            return redirect(url_for('register'))

        if not student_id:
            flash('请填写学号', 'danger')
            return redirect(url_for('register'))

        if not validate_student_id(student_id):
            flash('学号格式不正确！格式要求：前两位为26-31，后面为姓名全拼小写（如：29rentaowei）', 'danger')
            return redirect(url_for('register'))

        # 检查是否在禁止注册期内
        banned, days_left = is_student_id_banned(student_id)
        if banned:
            flash(f'该学号因违规被禁止注册，剩余 {days_left} 天后可重新注册', 'danger')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(student_id=student_id, account_type=account_type).first()
        if existing_user:
            if account_type == 'real':
                flash('该学号已注册过实名账号，不能重复注册', 'danger')
            else:
                flash('该学号已注册过匿名账号，不能重复注册', 'danger')
            return redirect(url_for('register'))

        if len(password) < 4:
            flash('密码至少4位', 'danger')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('两次密码不一致', 'danger')
            return redirect(url_for('register'))

        real_name = None
        username = None

        if account_type == 'real':
            real_name = request.form.get('real_name')
            if not real_name:
                flash('请填写真实姓名', 'danger')
                return redirect(url_for('register'))
            username = student_id
        else:
            username = generate_anonymous_username()

        if User.query.filter_by(username=username).first():
            if account_type == 'real':
                flash('该学号已被注册', 'danger')
            else:
                flash('系统错误，请重试', 'danger')
            return redirect(url_for('register'))

        user = User(
            email=f"{student_id}@huijia.edu.cn",
            username=username,
            password=generate_password_hash(password),
            account_type=account_type,
            real_name=real_name,
            student_id=student_id,
            is_verified=True
        )
        db.session.add(user)
        db.session.commit()

        flash('注册成功！请登录', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')
        account_type = request.form.get('account_type')

        user = User.query.filter_by(student_id=student_id, account_type=account_type).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if account_type == 'real':
                flash(f'欢迎回来，{user.real_name}！', 'success')
            else:
                flash('欢迎回来，匿名用户！', 'success')
            return redirect(url_for('index'))
        else:
            flash('学号、账号类型或密码错误', 'danger')

    return render_template('login.html')

@app.route('/new-post', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        section = request.form.get('section')

        if section not in SECTIONS:
            flash('请选择正确的版块', 'danger')
            return redirect(url_for('new_post'))

        if not title or len(title) < 2:
            flash('标题至少2个字符', 'danger')
            return redirect(url_for('new_post'))

        if not content or len(content) < 1:
            flash('内容不能为空', 'danger')
            return redirect(url_for('new_post'))

        has_sensitive, bad_word = check_sensitive_words(title)
        if has_sensitive:
            flash(f'标题包含敏感词: "{bad_word}"，请修改', 'danger')
            return redirect(url_for('new_post'))

        has_sensitive, bad_word = check_sensitive_words(content)
        if has_sensitive:
            flash(f'内容包含敏感词: "{bad_word}"，请修改', 'danger')
            return redirect(url_for('new_post'))

        # ========== 处理上传的附件 ==========
        uploaded_files = []
        files = request.files.getlist('attachments')
        for file in files:
            if file and allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                unique_name = f"{uuid.uuid4().hex}_{original_filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(save_path)
                uploaded_files.append(unique_name)
            elif file and file.filename != '':
                flash(f'不支持的文件类型: {file.filename}', 'danger')
                return redirect(url_for('new_post'))

        # 审核逻辑
        if section == 'confession':
            is_approved = False
            flash('内容将在24小时内审核', 'info')
        else:
            is_approved = True
            flash('发布成功！', 'success')

        post = Post(
            title=title,
            content=content,
            section=section,
            user_id=current_user.id,
            is_approved=is_approved,
            attachments=uploaded_files   # 存储路径列表
        )
        db.session.add(post)
        db.session.commit()

        if section == 'confession':
            return redirect(url_for('index'))
        else:
            return redirect(url_for('view_section', section_name=section))

    return render_template('new_post.html', sections=SECTIONS)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    if post.section == 'confession' and not post.is_approved and not (current_user.is_authenticated and current_user.is_admin):
        flash('该帖子正在审核中，暂不可见', 'warning')
        return redirect(url_for('index'))
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    return render_template('post_detail.html', post=post, comments=comments, sections=SECTIONS)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('content')
    post = Post.query.get_or_404(post_id)

    if not content or len(content) < 1:
        flash('评论内容不能为空', 'danger')
        return redirect(url_for('post_detail', post_id=post_id))

    has_sensitive, bad_word = check_sensitive_words(content)
    if has_sensitive:
        flash(f'评论包含敏感词: "{bad_word}"，请修改', 'danger')
        return redirect(url_for('post_detail', post_id=post_id))

    comment = Comment(content=content, user_id=current_user.id, post_id=post_id)
    db.session.add(comment)
    db.session.commit()
    flash('评论发布成功', 'success')
    return redirect(url_for('post_detail', post_id=post_id))

# ========== 删除功能（用户自删） ==========
@app.route('/delete-post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and not current_user.is_admin:
        flash('没有权限', 'danger')
        return redirect(url_for('index'))

    # 删除附件文件
    for file in post.attachments or []:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
        if os.path.exists(file_path):
            os.remove(file_path)

    section_name = post.section
    db.session.delete(post)
    db.session.commit()
    flash('帖子已删除', 'success')
    return redirect(url_for('view_section', section_name=section_name))

@app.route('/delete-comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.post_id
    if comment.user_id != current_user.id and not current_user.is_admin:
        flash('没有权限', 'danger')
        return redirect(url_for('post_detail', post_id=post_id))
    db.session.delete(comment)
    db.session.commit()
    flash('评论已删除', 'success')
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect('/')

# ========== 公告管理 ==========
@app.route('/admin/announcements')
@login_required
@admin_required
def admin_announcements():
    announcements = Announcement.query.order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc()
    ).all()
    return render_template('admin_announcements.html', announcements=announcements)

@app.route('/admin/announcement/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_announcement():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        is_pinned = request.form.get('is_pinned') == 'on'
        if not title or not content:
            flash('标题和内容都不能为空', 'danger')
            return redirect(url_for('new_announcement'))
        ann = Announcement(title=title, content=content, is_pinned=is_pinned, user_id=current_user.id)
        db.session.add(ann)
        db.session.commit()
        flash('公告发布成功！', 'success')
        return redirect(url_for('admin_announcements'))
    return render_template('new_announcement.html')

@app.route('/admin/announcement/edit/<int:announcement_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_announcement(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)
    if request.method == 'POST':
        ann.title = request.form.get('title')
        ann.content = request.form.get('content')
        ann.is_pinned = request.form.get('is_pinned') == 'on'
        db.session.commit()
        flash('公告已更新', 'success')
        return redirect(url_for('admin_announcements'))
    return render_template('edit_announcement.html', announcement=ann)

@app.route('/admin/announcement/delete/<int:announcement_id>')
@login_required
@admin_required
def delete_announcement(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)
    db.session.delete(ann)
    db.session.commit()
    flash('公告已删除', 'success')
    return redirect(url_for('admin_announcements'))

# ========== 管理面板 ==========
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    users = User.query.all()
    pending_count = Post.query.filter_by(section='confession', is_approved=False).count()
    return render_template('admin_dashboard.html', posts=posts, users=users, pending_count=pending_count)

@app.route('/admin/delete-post/<int:post_id>')
@login_required
@admin_required
def admin_delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    # 删除附件文件
    for file in post.attachments or []:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
        if os.path.exists(file_path):
            os.remove(file_path)
    db.session.delete(post)
    db.session.commit()
    flash('帖子已删除', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-comment/<int:comment_id>')
@login_required
@admin_required
def admin_delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('评论已删除', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/make-admin/<int:user_id>')
@login_required
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f'{user.username} 已成为管理员', 'success')
    return redirect(url_for('admin_dashboard'))

# ========== 删除用户（带禁注册选项） ==========
@app.route('/admin/delete-user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('不能删除自己的账号', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        ban_days = int(request.form.get('ban_days', 0))
        student_id = user.student_id

        # 删除用户（级联删除会自动删除其帖子和评论，但附件需要手动删除）
        for post in user.posts:
            for file in post.attachments or []:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
                if os.path.exists(file_path):
                    os.remove(file_path)
        db.session.delete(user)
        db.session.commit()

        if 1 <= ban_days <= 7:
            banned_until = datetime.now() + timedelta(days=ban_days)
            ban_record = BannedRegistration(
                student_id=student_id,
                banned_until=banned_until,
                reason=f'管理员删除账号时设置，禁止注册{ban_days}天'
            )
            db.session.add(ban_record)
            db.session.commit()
            flash(f'已删除用户 {student_id}，并禁止该学号注册 {ban_days} 天', 'success')
        else:
            flash(f'已删除用户 {student_id}', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_delete_user_confirm.html', user=user)

# ========== 表白墙审核 ==========
@app.route('/admin/pending-posts')
@login_required
@admin_required
def pending_posts():
    pending = Post.query.filter_by(section='confession', is_approved=False).order_by(Post.created_at.desc()).all()
    return render_template('admin_pending.html', pending=pending)

@app.route('/admin/approve-post/<int:post_id>', methods=['POST'])
@login_required
@admin_required
def approve_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.section == 'confession' and not post.is_approved:
        post.is_approved = True
        db.session.commit()
        flash('帖子已通过审核', 'success')
    else:
        flash('帖子无需审核或已审核', 'warning')
    return redirect(url_for('pending_posts'))

@app.route('/admin/reject-post/<int:post_id>', methods=['POST'])
@login_required
@admin_required
def reject_post(post_id):
    post = Post.query.get_or_404(post_id)
    reason = request.form.get('reason')
    if post.section == 'confession' and not post.is_approved:
        # 拒绝时删除附件
        for file in post.attachments or []:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
            if os.path.exists(file_path):
                os.remove(file_path)
        db.session.delete(post)
        db.session.commit()
        flash(f'已拒绝帖子，原因：{reason}', 'danger')
    else:
        flash('操作无效', 'warning')
    return redirect(url_for('pending_posts'))

# ========== 数据库初始化 ==========
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=88)