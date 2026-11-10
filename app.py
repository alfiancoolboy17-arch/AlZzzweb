
import os
import csv
import io
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session,
    flash, render_template_string, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("ALZZZ_SECRET", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DB = "alzzz.db"
UPLOAD = "static_uploads"
os.makedirs(UPLOAD, exist_ok=True)

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            photo TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            note TEXT DEFAULT '',
            date TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            position TEXT NOT NULL,
            entry REAL DEFAULT 0,
            exit_price REAL DEFAULT 0,
            result REAL DEFAULT 0,
            note TEXT DEFAULT '',
            date TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS evaluations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            criticism TEXT DEFAULT '',
            suggestion TEXT DEFAULT '',
            UNIQUE(user_id, month),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)

        # Buat admin pertama melalui environment variable.
        admin_name = os.environ.get("ADMIN_USER")
        admin_pass = os.environ.get("ADMIN_PASSWORD")
        if admin_name and admin_pass:
            exists = c.execute(
                "SELECT id FROM users WHERE username=?", (admin_name,)
            ).fetchone()
            if not exists:
                c.execute(
                    "INSERT INTO users(username,password,role) VALUES(?,?,?)",
                    (admin_name, generate_password_hash(admin_pass), "admin")
                )

init_db()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return wrapper

def money(n):
    return "Rp " + format(int(n), ",").replace(",", ".")

BASE = """
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlZzz Web</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap');
:root{--bg:#060611;--panel:#101024;--panel2:#17172f;--cyan:#24eaff;--purple:#a855f7;--pink:#ff42c8;--green:#20f5a5;--red:#ff4f86;--gold:#ffd166;--text:#f4f2ff;--muted:#9da4c2;--line:#34345f}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;min-height:100vh;color:var(--text);font-family:Inter,Arial,sans-serif;background:radial-gradient(ellipse at 12% 0%,#48207855,transparent 34%),radial-gradient(ellipse at 92% 12%,#075b8750,transparent 32%),linear-gradient(145deg,#05050d,#0a0b1d 52%,#10091c);background-attachment:fixed}
body:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;opacity:.22;background-image:linear-gradient(#8b5cf615 1px,transparent 1px),linear-gradient(90deg,#8b5cf615 1px,transparent 1px);background-size:34px 34px}
a,button{cursor:pointer;text-decoration:none;color:inherit}header{position:sticky;top:0;z-index:50;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;padding:16px max(18px,calc((100% - 1220px)/2));background:#080817eF;border-bottom:1px solid #7541a866;backdrop-filter:blur(18px);box-shadow:0 8px 35px #0008}
.logo{font-family:Orbitron,Inter,sans-serif;font-size:clamp(20px,3vw,29px);font-weight:800;letter-spacing:1px;background:linear-gradient(90deg,var(--cyan),#9d6bff,var(--pink));-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 10px #00eaff55)}nav{display:flex;gap:8px;flex-wrap:wrap}nav a,.btn{display:inline-flex;align-items:center;justify-content:center;padding:10px 13px;border:1px solid #484276;border-radius:11px;background:linear-gradient(145deg,#1b1b39,#11152b);font-size:13px;font-weight:700;transition:.22s}nav a:hover,.btn:hover{border-color:var(--cyan);box-shadow:0 0 18px #00dfff55;transform:translateY(-2px);color:white}
main{width:min(1220px,100%);margin:auto;padding:24px 20px 36px}.card{position:relative;overflow:hidden;background:linear-gradient(145deg,#17172fef,#0d1023f5);border:1px solid #45406d;border-radius:19px;padding:21px;margin-bottom:17px;box-shadow:0 12px 34px #0004,inset 0 0 25px #a855f70a;transition:transform .22s,border-color .22s,box-shadow .22s}.card:after{content:"";position:absolute;top:0;left:8%;right:8%;height:1px;background:linear-gradient(90deg,transparent,#8b5cf7aa,transparent)}.card:hover{border-color:#5d9dbb;box-shadow:0 12px 34px #0005,0 0 22px #8b5cf722}h2,h3{margin-top:0;color:var(--cyan);font-family:Orbitron,Inter,sans-serif;letter-spacing:.3px}h2{font-size:clamp(19px,3vw,26px)}h3{font-size:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:15px}.stat{font-family:Orbitron,Inter,sans-serif;font-size:clamp(22px,3vw,29px);font-weight:800;margin-top:12px;text-shadow:0 0 15px currentColor}.green{color:var(--green)}.red{color:var(--pink)}.muted{color:var(--muted);font-size:13px;line-height:1.6}
input,select,textarea{display:block;width:100%;padding:13px 14px;margin:7px 0 14px;border-radius:11px;background:#090b1b;color:white;border:1px solid #48436e;outline:none;font:inherit}input:focus,select:focus,textarea:focus{border-color:var(--cyan);box-shadow:0 0 0 3px #00eaff18,0 0 15px #00eaff22}button,.submit{border:1px solid #a36cff;border-radius:11px;color:white;padding:12px 18px;font-weight:800;background:linear-gradient(105deg,#6326bb,#087eae,#a52ac7);background-size:200% 100%;box-shadow:0 5px 18px #8b38ff33;transition:.2s}button:hover,.submit:hover{background-position:100% 0;box-shadow:0 0 22px #00eaff66;transform:translateY(-2px)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:12px 11px;border-bottom:1px solid #30304f;text-align:left}th{color:var(--cyan);background:#211b3a;font-family:Orbitron,Inter,sans-serif;font-size:11px;letter-spacing:.4px}td{background:#111329}tr:hover td{background:#1b1a38}.table-wrap{overflow-x:auto;border-radius:12px}.alert{padding:13px 15px;background:#142b43;border:1px solid #287b9b;border-radius:12px;margin:10px 0 16px;box-shadow:0 0 16px #00dfff16}.quote{font-style:italic;color:#e2c8ff;line-height:1.7}.profile{width:65px;height:65px;object-fit:cover;border-radius:50%;border:2px solid var(--cyan);box-shadow:0 0 18px #00dfff77}footer{text-align:center;padding:28px;color:var(--muted);font-size:12px;letter-spacing:1px;border-top:1px solid #30264c}form.inline{display:inline}
.hero{display:grid;grid-template-columns:1.5fr .8fr;gap:18px;align-items:center;min-height:190px;background:radial-gradient(circle at 85% 20%,#792bd744,transparent 34%),linear-gradient(120deg,#171735,#10162b 65%,#211137);border-color:#7250a5}.hero-title{font-family:Orbitron,Inter,sans-serif;font-size:clamp(23px,4vw,36px);font-weight:800;line-height:1.25;background:linear-gradient(90deg,#fff,var(--cyan),#c99aff);-webkit-background-clip:text;background-clip:text;color:transparent}.hero-side{padding:17px;border:1px solid #6d4a9b;border-radius:16px;background:#090b1c88;text-align:center}.eyebrow{font-size:10px;letter-spacing:2px;color:#c2a4ff;font-weight:800}.quick-links{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.quick-links a{padding:13px 9px;text-align:center;border:1px solid #46406c;border-radius:13px;background:#15152d;font-size:12px;font-weight:700}.quick-links a:hover{border-color:var(--cyan);box-shadow:0 0 16px #00dfff33}.progress{height:9px;background:#292743;border-radius:20px;overflow:hidden;margin-top:10px}.progress span{display:block;height:100%;border-radius:20px;background:linear-gradient(90deg,var(--cyan),var(--purple),var(--pink));box-shadow:0 0 12px #a855f7}.stat-card{min-height:118px}.stat-label{font-size:12px;color:var(--muted);letter-spacing:.8px;text-transform:uppercase}.chart-grid{display:grid;grid-template-columns:1.5fr .8fr;gap:16px}.chart-box{min-width:0;min-height:260px}.chart-box canvas{max-height:300px}.section-label{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}.section-label small{color:var(--muted)}
@media(max-width:720px){header{position:relative;padding:14px}nav{width:100%;flex-wrap:nowrap;overflow-x:auto;padding:3px 1px 8px;scrollbar-width:thin}nav a{white-space:nowrap;flex:0 0 auto;font-size:12px}main{padding:14px 12px 28px}.hero{grid-template-columns:1fr}.hero-side{display:none}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.card{padding:16px;border-radius:16px;margin-bottom:12px}.stat{font-size:20px}.chart-grid{grid-template-columns:1fr}.quick-links{grid-template-columns:repeat(2,1fr)}th,td{padding:10px 8px;white-space:nowrap}}
@media(max-width:370px){.grid{grid-template-columns:1fr}.logo{font-size:20px}}

/* ===== ALZZZ LOGIN CENTER ===== */

body:has(input[type="password"]) main {
    width: min(92%, 460px);
    max-width: 460px;
    min-height: calc(100svh - 180px);
    margin-left: auto !important;
    margin-right: auto !important;
    display: flex;
    align-items: center;
    justify-content: center;
}

body:has(input[type="password"]) main > * {
    width: 100%;
    max-width: 460px;
    margin-left: auto !important;
    margin-right: auto !important;
}

body:has(input[type="password"]) main .card {
    width: 100%;
    max-width: 460px;
    padding: 25px;
    border-radius: 22px;
    text-align: center;
    box-shadow: 0 0 30px #00dfff22,
                0 0 50px #a855ff22;
}

body:has(input[type="password"]) input,
body:has(input[type="password"]) button {
    width: 100%;
}

body:has(input[type="password"]) main h2 {
    text-align: center;
    color: #00eaff;
    letter-spacing: 2px;
    margin-bottom: 25px;
}

@media(max-width: 480px) {
    body:has(input[type="password"]) main {
        width: 92%;
        min-height: calc(100svh - 150px);
    }
}

</style>
</head>
<body>
<header>
 <div class="logo"> AlZzz Web</div>
 {% if user %}
 <nav>
  <a href="/">Dashboard</a>
  <a href="/transactions">Keuangan</a>
  <a href="/trading">Trading</a>
  <a href="/evaluation">Evaluasi</a>
  <a href="/profile">Profil</a>
  {% if user.role == 'admin' %}<a href="/admin">Admin</a>{% endif %}
  <a href="/logout">Keluar</a>
 </nav>
 {% endif %}
</header>
<main>
{% with messages = get_flashed_messages() %}
 {% for msg in messages %}<div class="alert">{{msg}}</div>{% endfor %}
{% endwith %}
{{ content|safe }}
</main>
<footer> ALZZZ WEB • FINANCIAL CONTROL SYSTEM </footer>
</body>
</html>
"""

def page(content, **kwargs):
    user = None
    if session.get("uid"):
        with db() as c:
            user = c.execute(
                "SELECT * FROM users WHERE id=?", (session["uid"],)
            ).fetchone()
    return render_template_string(
        BASE, content=render_template_string(content, **kwargs), user=user
    )

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("username","").strip()
        pw = request.form.get("password","")
        if len(name) < 3 or len(pw) < 8:
            flash("Nama minimal 3 karakter dan password minimal 8 karakter.")
        else:
            try:
                with db() as c:
                    c.execute(
                        "INSERT INTO users(username,password) VALUES(?,?)",
                        (name,generate_password_hash(pw))
                    )
                flash("Pendaftaran berhasil. Silakan login.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Nama akun sudah digunakan.")
    return page("""
    <div class="card" style="max-width:430px;margin:40px auto">
    <h2> Buat Akun</h2>
    <form method="post">
    Nama akun<input name="username" required minlength="3">
    Password<input name="password" type="password" required minlength="8">
    <button class="submit">Daftar</button>
    </form><a href="/login">Sudah punya akun? Login</a>
    </div>""")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        name = request.form.get("username","")
        pw = request.form.get("password","")
        with db() as c:
            u = c.execute("SELECT * FROM users WHERE username=?", (name,)).fetchone()
        if u and check_password_hash(u["password"],pw):
            session.clear()
            session["uid"] = u["id"]
            session["role"] = u["role"]
            session["name"] = u["username"]
            flash("Selamat datang " + u["username"] + "!")
            return redirect(url_for("home"))
        flash("Nama akun atau password salah.")
    return page("""
    <div class="card" style="max-width:430px;margin:40px auto">
    <h2> LOGIN</h2>
    <form method="post">
    Nama akun<input name="username" required>
    Password<input name="password" type="password" required>
    <button class="submit">Masuk</button>
    </form><a href="/register">Belum punya akun? Daftar</a>
    </div>""")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def home():
    with db() as c:
        rows = c.execute("""
        SELECT kind,SUM(amount) total FROM transactions
        WHERE user_id=? AND strftime('%Y-%m',date)=?
        GROUP BY kind
        """,(session["uid"],datetime.now().strftime("%Y-%m"))).fetchall()

        history = c.execute("""
        SELECT * FROM transactions WHERE user_id=?
        ORDER BY date DESC,id DESC LIMIT 7
        """,(session["uid"],)).fetchall()

    income = sum(r["total"] for r in rows if r["kind"]=="income")
    expense = sum(r["total"] for r in rows if r["kind"]=="expense")
    balance = income-expense
    with db() as c:
        transaction_count = c.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id=?", (session["uid"],)
        ).fetchone()[0]
    xp = transaction_count * 20
    level = xp // 100 + 1
    progress = xp % 100

    if expense > income and expense > 0:
        comment = "⚠️ Pengeluaran lebih besar dari pemasukan. Evaluasi pengeluaranmu!"
    elif expense > income * .7 and expense > 0:
        comment = "💡 Pengeluaran cukup tinggi. Mulai atur prioritas!"
    elif expense > 0:
        comment = "🔥 Pengeluaran masih terkendali. Pertahankan!"
    else:
        comment = "🚀 Yuk mulai catat keuanganmu!"

    if income >= 10000000:
        income_comment = "🏆 Pemasukan bulan ini besar! Tetap bijak mengelolanya."
    elif income > 0:
        income_comment = "🌱 Pemasukan mulai tercatat. Terus kembangkan!"
    else:
        income_comment = "💼 Belum ada pemasukan tercatat bulan ini."

    labels = []
    ins = []
    outs = []
    with db() as c:
        for i in range(1,13):
            month = datetime.now().strftime("%Y") + f"-{i:02d}"
            labels.append(month)
            data = c.execute("""
            SELECT kind,SUM(amount) total FROM transactions
            WHERE user_id=? AND strftime('%Y-%m',date)=?
            GROUP BY kind
            """,(session["uid"],month)).fetchall()
            ins.append(next((r["total"] or 0 for r in data if r["kind"]=="income"),0))
            outs.append(next((r["total"] or 0 for r in data if r["kind"]=="expense"),0))

    return page("""
    <section class="card hero">
      <div>
        <div class="eyebrow"> YOUR FINANCIAL QUEST STARTS HERE</div>
        <div class="hero-title">Selamat Datang,<br>{{name}}!</div>
        <div id="clock" style="font-size:16px;color:var(--green);margin-top:13px"></div>
        <p id="hijri" class="muted"></p>
        <p class="muted">Bulan laporan: {{month}}</p>
      </div>
      <div class="hero-side">
        <div style="font-size:34px">🏆</div>
        <div class="eyebrow">PLAYER LEVEL</div>
        <div style="font:800 30px Orbitron;color:var(--gold)">LVL {{level}}</div>
        <div class="muted">{{xp}} XP • {{transaction_count}} transaksi tercatat</div>
        <div class="progress"><span style="width:{{progress}}%"></span></div>
        <div class="muted">{{progress}} / 100 XP menuju level berikutnya</div>
      </div>
    </section>
    <section class="quick-links" style="margin-bottom:17px">
      <a href="/transactions">💰<br>Catat Keuangan</a>
      <a href="/trading">📈<br>Trading Journal</a>
      <a href="/evaluation">🎯<br>Evaluasi</a>
      <a href="/profile">👤<br>Profil Saya</a>
    </section>
    <div class="grid">
      <div class="card stat-card"><div class="stat-label">💎 Total Pemasukan</div><div class="stat green">{{money(income)}}</div><div class="muted">Bulan ini</div></div>
      <div class="card stat-card"><div class="stat-label"> Total Pengeluaran</div><div class="stat red">{{money(expense)}}</div><div class="muted">Bulan ini</div></div>
      <div class="card stat-card"><div class="stat-label">🪙 Saldo Bersih</div><div class="stat">{{money(balance)}}</div><div class="muted">Pemasukan dikurangi pengeluaran</div></div>
    </div>
    <div class="chart-grid">
      <div class="card chart-box"><div class="section-label"><h3>📊 Financial Performance</h3><small>12 bulan</small></div><canvas id="chart"></canvas></div>
      <div class="card chart-box"><h3>🎮 Money Balance</h3><canvas id="mixChart"></canvas><p class="muted" style="text-align:center">Perbandingan pemasukan dan pengeluaran bulan ini</p></div>
    </div>
    <div class="grid">
      <div class="card"><h3>📢 Quest Evaluation</h3><p>{{comment}}</p><p>{{income_comment}}</p></div>
      <div class="card"><h3>💡 Daily Mindset</h3><p class="quote" id="quote"></p><div class="eyebrow">DISCIPLINE • CONSISTENCY • GROWTH</div></div>
    </div>
    <div class="card">
      <div class="section-label"><h3>📝 Recent Transactions</h3><a class="btn" href="/transactions">Lihat semua</a></div>
      <div class="table-wrap"><table><tr><th>Tanggal</th><th>Jenis</th><th>Keterangan</th><th>Nominal</th></tr>
      {% for r in history %}<tr><td>{{r.date}}</td><td>{{'Pemasukan' if r.kind=='income' else 'Pengeluaran'}}</td><td>{{r.category}} - {{r.note}}</td><td>{{money(r.amount)}}</td></tr>
      {% else %}<tr><td colspan="4">Belum ada transaksi. Mulai catat keuanganmu!</td></tr>{% endfor %}
      </table></div>
    </div>
    <script>
    function updateClock(){
      const d=new Date();
      document.getElementById('clock').textContent=d.toLocaleDateString('id-ID',{weekday:'long',day:'numeric',month:'long',year:'numeric'})+' • '+d.toLocaleTimeString('id-ID');
      try{document.getElementById('hijri').textContent='Kalender Hijriah: '+new Intl.DateTimeFormat('id-ID-u-ca-islamic-umalqura',{day:'numeric',month:'long',year:'numeric'}).format(d)}catch(e){}
    }
    updateClock();setInterval(updateClock,1000);
    Chart.defaults.color='#b9bdd5';Chart.defaults.font.family='Inter,Arial,sans-serif';
    new Chart(document.getElementById('chart'),{type:'bar',data:{labels:{{labels|tojson}},datasets:[
      {label:'Pemasukan',data:{{ins|tojson}},backgroundColor:'rgba(32,245,165,.78)',borderColor:'#20f5a5',borderWidth:1,borderRadius:7},
      {label:'Pengeluaran',data:{{outs|tojson}},backgroundColor:'rgba(255,66,200,.72)',borderColor:'#ff42c8',borderWidth:1,borderRadius:7}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{usePointStyle:true,boxWidth:8}}},scales:{x:{grid:{display:false}},y:{beginAtZero:true,grid:{color:'#ffffff12'}}}}});
    new Chart(document.getElementById('mixChart'),{type:'doughnut',data:{labels:['Pemasukan','Pengeluaran'],datasets:[{data:[{{income}},{{expense}}],backgroundColor:['#20f5a5','#ff42c8'],borderColor:'#111329',borderWidth:4,hoverOffset:8}]},options:{responsive:true,maintainAspectRatio:false,cutout:'70%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:8}}}}});
    const quotes=['Bangun kebiasaan finansial yang kuat, satu keputusan bijak setiap hari.','Konsistensi kecil hari ini dapat membentuk masa depan yang lebih baik.','Kuasai cara mengelola uang sebelum mengejar jumlah yang lebih besar.','Disiplin adalah fondasi dari setiap target yang ingin dicapai.','Investasi pada pengetahuan dan kemampuan diri selalu layak diperjuangkan.'];
    document.getElementById('quote').textContent=quotes[Math.floor(Math.random()*quotes.length)];
    </script>
    """,name=session["name"],month=datetime.now().strftime("%B %Y"),
    income=income,expense=expense,balance=balance,money=money,
    comment=comment,income_comment=income_comment,history=history,
    labels=labels,ins=ins,outs=outs,level=level,xp=xp,progress=progress,
    transaction_count=transaction_count)

@app.route("/transactions", methods=["GET","POST"])
@login_required
def transactions():
    uid=session["uid"]
    if request.method=="POST":
        try:
            kind=request.form["kind"]
            amount=float(request.form["amount"])
            category=request.form["category"].strip()
            note=request.form.get("note","").strip()
            date=request.form["date"]
            if kind not in ("income","expense") or amount<=0:
                raise ValueError()
            datetime.strptime(date,"%Y-%m-%d")
            if len(category)>60 or len(note)>300:
                raise ValueError()
            with db() as c:
                c.execute("""INSERT INTO transactions
                (user_id,kind,amount,category,note,date)
                VALUES(?,?,?,?,?,?)""",(uid,kind,amount,category,note,date))
            flash("Transaksi berhasil disimpan.")
        except (ValueError,KeyError):
            flash("Data transaksi tidak valid.")
        return redirect(url_for("transactions"))

    with db() as c:
        rows=c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC,id DESC",(uid,)).fetchall()

    return page("""
    <div class="card"><h2>💰 Catat Keuangan</h2>
    <form method="post">
    Jenis transaksi<select name="kind"><option value="income">Pemasukan</option><option value="expense">Pengeluaran</option></select>
    Nominal (Rupiah)<input type="number" name="amount" min="1" step="1" required>
    Kategori<select name="category">
    {% for x in ['Gaji','Bisnis','Freelance','Investasi','Makan','Minum','Transportasi','Belanja','Tagihan','Pendidikan','Kesehatan','Hiburan','Lainnya'] %}
    <option>{{x}}</option>{% endfor %}
    </select>
    Keterangan<textarea name="note" maxlength="300" placeholder="Contoh: makan siang, gaji bulanan..."></textarea>
    Tanggal<input type="date" name="date" value="{{today}}" required>
    <button>Simpan Transaksi</button></form></div>
    <div class="card"><h3>📋 Riwayat Keuangan</h3>
    <div class="table-wrap"><table><tr><th>Tanggal</th><th>Jenis</th><th>Kategori</th><th>Nominal</th></tr>
    {% for r in rows %}<tr><td>{{r.date}}</td><td>{{r.kind}}</td>
    <td>{{r.category}} {{r.note}}</td><td>{{money(r.amount)}}</td></tr>
    {% else %}<tr><td colspan="4">Belum ada data.</td></tr>{% endfor %}
    </table></div></div>
    <div class="card"><h3>📥 Download Rekap Bulanan</h3>
    <form action="/export" method="get">
    <input type="month" name="month" value="{{month}}" required>
    <button>Download CSV</button></form></div>
    """,rows=rows,today=datetime.now().strftime("%Y-%m-%d"),
    month=datetime.now().strftime("%Y-%m"),money=money)

@app.route("/export")
@login_required
def export():
    month=request.args.get("month",datetime.now().strftime("%Y-%m"))
    try:
        datetime.strptime(month,"%Y-%m")
    except ValueError:
        abort(400)
    with db() as c:
        rows=c.execute("""SELECT date,kind,category,note,amount
        FROM transactions WHERE user_id=? AND strftime('%Y-%m',date)=?
        ORDER BY date""",(session["uid"],month)).fetchall()
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(["Tanggal","Jenis","Kategori","Keterangan","Nominal"])
    for r in rows:
        writer.writerow(list(r))
    data=io.BytesIO(("\ufeff"+output.getvalue()).encode("utf-8"))
    return send_file(data,mimetype="text/csv",
        as_attachment=True,download_name="AlZzz-Rekap-"+month+".csv")

@app.route("/trading", methods=["GET","POST"])
@login_required
def trading():
    uid=session["uid"]
    if request.method=="POST":
        try:
            asset=request.form["asset"].strip()
            position=request.form["position"]
            entry=float(request.form["entry"])
            exitp=float(request.form["exit_price"])
            note=request.form.get("note","").strip()
            date=request.form["date"]
            if not asset or len(asset)>40 or position not in ("BUY","SELL"):
                raise ValueError()
            datetime.strptime(date,"%Y-%m-%d")
            with db() as c:
                c.execute("""INSERT INTO trades
                (user_id,asset,position,entry,exit_price,result,note,date)
                VALUES(?,?,?,?,?,?,?,?)""",
                (uid,asset,position,entry,exitp,exitp-entry,note,date))
            flash("Jurnal trading disimpan.")
        except (ValueError,KeyError):
            flash("Data trading tidak valid.")
        return redirect(url_for("trading"))
    with db() as c:
        rows=c.execute("SELECT * FROM trades WHERE user_id=? ORDER BY date DESC,id DESC",(uid,)).fetchall()
    return page("""
    <div class="card"><h2>📈 Trading Journal</h2>
    <form method="post">
    Aset / Pair<input name="asset" placeholder="Contoh: BTC/USDT" required maxlength="40">
    Posisi<select name="position"><option>BUY</option><option>SELL</option></select>
    Harga masuk<input type="number" step="any" name="entry" required>
    Harga keluar<input type="number" step="any" name="exit_price" required>
    Tanggal<input type="date" name="date" value="{{today}}" required>
    Evaluasi<textarea name="note" placeholder="Alasan entry, rencana, pelajaran..." maxlength="300"></textarea>
    <button>Simpan Jurnal</button></form>
    <p class="muted">Catatan hasil dihitung dari selisih harga keluar dan masuk, bukan profit bersih. Untuk posisi SELL, interpretasikan hasil secara terbalik.</p>
    </div>
    <div class="card"><h3>Riwayat Trading</h3>
    <div class="table-wrap"><table><tr><th>Tanggal</th><th>Aset</th><th>Posisi</th><th>Entry</th><th>Exit</th><th>Selisih</th><th>Catatan</th></tr>
    {% for r in rows %}<tr><td>{{r.date}}</td><td>{{r.asset}}</td><td>{{r.position}}</td>
    <td>{{r.entry}}</td><td>{{r.exit_price}}</td>
    <td>{{r.exit_price-r.entry}}</td><td>{{r.note}}</td></tr>
    {% else %}<tr><td colspan="7">Belum ada jurnal.</td></tr>{% endfor %}
    </table></div></div>
    """,rows=rows,today=datetime.now().strftime("%Y-%m-%d"))

@app.route("/evaluation",methods=["GET","POST"])
@login_required
def evaluation():
    uid=session["uid"]
    month=datetime.now().strftime("%Y-%m")
    if request.method=="POST":
        criticism=request.form.get("criticism","")[:2000]
        suggestion=request.form.get("suggestion","")[:2000]
        with db() as c:
            c.execute("""INSERT INTO evaluations(user_id,month,criticism,suggestion)
            VALUES(?,?,?,?) ON CONFLICT(user_id,month) DO UPDATE SET
            criticism=excluded.criticism,suggestion=excluded.suggestion""",
            (uid,month,criticism,suggestion))
        flash("Evaluasi bulanan berhasil disimpan.")
        return redirect(url_for("evaluation"))
    with db() as c:
        old=c.execute("SELECT * FROM evaluations WHERE user_id=? AND month=?",
        (uid,month)).fetchone()
    return page("""
    <div class="card"><h2>📝 Evaluasi Bulanan</h2>
    <p>Bulan {{month}}</p>
    <form method="post">
    Kritik terhadap pengelolaan keuangan<textarea name="criticism" rows="5">{{old.criticism if old else ''}}</textarea>
    Saran dan target bulan berikutnya<textarea name="suggestion" rows="5">{{old.suggestion if old else ''}}</textarea>
    <button>Simpan Evaluasi</button>
    </form></div>
    """,month=month,old=old)

@app.route("/profile",methods=["GET","POST"])
@login_required
def profile():
    uid=session["uid"]
    with db() as c:
        u=c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    if request.method=="POST":
        name=request.form.get("username","").strip()
        old=request.form.get("old_password","")
        new=request.form.get("new_password","")
        photo=request.files.get("photo")
        if not check_password_hash(u["password"],old):
            flash("Password lama salah.")
        elif len(name)<3 or len(new)<8:
            flash("Nama minimal 3 karakter dan password baru minimal 8 karakter.")
        else:
            filename=u["photo"]
            if photo and photo.filename:
                ext=os.path.splitext(secure_filename(photo.filename))[1].lower()
                if ext not in (".png",".jpg",".jpeg",".webp"):
                    flash("Foto harus PNG, JPG, JPEG atau WEBP.")
                    return redirect(url_for("profile"))
                filename=secrets.token_hex(16)+ext
                photo.save(os.path.join(UPLOAD,filename))
            try:
                with db() as c:
                    c.execute("""UPDATE users SET username=?,password=?,photo=?
                    WHERE id=?""",(name,generate_password_hash(new),filename,uid))
                session["name"]=name
                flash("Profil berhasil diperbarui.")
                return redirect(url_for("profile"))
            except sqlite3.IntegrityError:
                flash("Nama akun sudah dipakai.")
    return page("""
    <div class="card"><h2>👤 Pengaturan Profil</h2>
    {% if u.photo %}<img class="profile" src="/uploads/{{u.photo}}">{% endif %}
    <form method="post" enctype="multipart/form-data">
    Nama akun baru<input name="username" value="{{u.username}}" required>
    Foto profil<input type="file" name="photo" accept="image/png,image/jpeg,image/webp">
    Password lama<input name="old_password" type="password" required>
    Password baru<input name="new_password" type="password" minlength="8" required>
    <button>Simpan Perubahan</button>
    </form></div>
    """,u=u)

@app.route("/uploads/<filename>")
@login_required
def uploads(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD,filename)

@app.route("/admin",methods=["GET","POST"])
@login_required
@admin_required
def admin():
    if request.method=="POST":
        name=request.form.get("username","").strip()
        pw=request.form.get("password","")
        role=request.form.get("role","member")
        if len(name)<3 or len(pw)<8 or role not in ("admin","member"):
            flash("Data akun tidak valid.")
        else:
            try:
                with db() as c:
                    c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                    (name,generate_password_hash(pw),role))
                flash("Akun berhasil dibuat.")
            except sqlite3.IntegrityError:
                flash("Nama akun sudah digunakan.")
        return redirect(url_for("admin"))

    with db() as c:
        users=c.execute("SELECT id,username,role,photo FROM users ORDER BY id").fetchall()
    return page("""
    <div class="card"><h2>🛡️ ADMIN CONTROL</h2>
    <p>Total akun terdaftar: {{users|length}}</p>
    <h3>Tambah Admin / Member</h3>
    <form method="post">
    Nama akun<input name="username" required minlength="3">
    Password<input name="password" type="password" required minlength="8">
    Hak akses<select name="role"><option value="member">Member</option><option value="admin">Admin</option></select>
    <button>Buat Akun</button></form></div>
    <div class="card"><h3>👥 Daftar Member dan Admin</h3>
    <div class="table-wrap"><table><tr><th>ID</th><th>Nama</th><th>Role</th></tr>
    {% for u in users %}<tr><td>{{u.id}}</td><td>{{u.username}}</td><td>{{u.role}}</td></tr>{% endfor %}
    </table></div></div>
    """,users=users)

@app.errorhandler(403)
def forbidden(e):
    return "Akses ditolak. Halaman ini khusus admin.",403

@app.errorhandler(413)
def too_large(e):
    return "Ukuran file terlalu besar. Maksimal 3 MB.",413

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000,debug=False)
