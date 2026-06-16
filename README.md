<img width="1510" height="854" alt="截屏2026-06-16 14 10 32" src="https://github.com/user-attachments/assets/e3c167c3-c8fe-4e8e-8da0-0fb3e6cd979a" />


# 汇佳学生论坛 (Huijia Student Forum)

一个为北京市私立汇佳学校学生设计的轻量级校园论坛，支持学号注册、实名/匿名双账号、表白墙审核、管理员封禁等核心功能。

## ✨ 功能特性

- **学号注册**：仅限汇佳学生（学号格式：`26-31` 开头 + 姓名全拼小写，例如 `29rentaowei`）
- **双账号模式**：同一学号可分别注册「实名账号」（显示真实姓名）和「匿名账号」（显示“匿名用户”），保护隐私
- **版块分区**：
  - 💕 表白墙（所有帖子需管理员审核，防止骚扰）
  - 📰 校园新闻
  - 📚 学术讨论
  - 💬 综合讨论
- **管理员功能**：
  - 删除任意帖子/评论
  - 封禁用户（3–7 天，自动解封）
  - 删除账号并禁止同一学号重新注册（1–7 天）
  - 发布置顶公告
  - 审核表白墙帖子
- **附件上传**：支持图片（jpg, png, gif, webp）和文件（pdf, doc, zip 等）
- **敏感词过滤**：自动拦截涉黄、脏话等违规内容
- **响应式界面**：基于 Bootstrap 5，适配电脑、平板、手机

## 🛠️ 技术栈

| 类别       | 技术                                            |
| ---------- | ----------------------------------------------- |
| 后端框架   | Flask (Python 3.13+)                           |
| 数据库     | SQLite                                          |
| 前端       | Bootstrap 5 + Font Awesome 6 + 自定义 CSS      |
| 认证       | Flask-Login + Werkzeug 密码哈希                |
| 模板引擎   | Jinja2                                          |

## 🚀 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/Cathy_x/huijia_forum_campus.git
cd huijia_forum_campus
```

### 2. 创建虚拟环境并安装依赖
```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 初始化数据库
```bash
python app.py   # 第一次运行会自动创建 forum.db
```

### 4. 设置管理员
注册一个实名账号后，在 Python 交互模式中执行：
```python
from app import app, db, User
with app.app_context():
    user = User.query.filter_by(student_id='你的学号').first()
    user.is_admin = True
    db.session.commit()
```

### 5. 运行
```bash
python app.py
```
访问 `http://127.0.0.1:88`

## 📁 项目结构

```
huijia_forum_campus/
├── app.py                 # 主应用与路由
├── models.py              # 数据库模型
├── requirements.txt       # 依赖列表
├── templates/             # Jinja2 模板
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── new_post.html
│   ├── post_detail.html
│   ├── section.html
│   ├── admin_dashboard.html
│   ├── admin_pending.html
│   ├── admin_announcements.html
│   └── ...
├── static/                # 静态资源 (CSS, 图片)
└── uploads/               # 上传文件目录
```

## ⚙️ 配置

在 `app.py` 中修改以下配置：

```python
app.config['SECRET_KEY'] = 'your-secret-key'      # 改为随机字符串
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
```

## 📄 开源协议

MIT License

## 📧 联系方式

项目维护者：29majiale & 29rentaowei

---

**注意**：本项目仅用于校内学习与交流，严禁用于商业用途。所有用户必须遵守文明公约，管理员有权封禁违规账号。
