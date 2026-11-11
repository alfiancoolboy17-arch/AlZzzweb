import os
import sqlite3
from functools import wraps
from datetime import date, datetime
from flask import Flask, g, request, redirect, url_for, session, flash, render_template_string, get_flashed_messages, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- PENGATURAN OTOMATIS DATABASE ---
if os.environ.get("DATABASE_PATH"):
    DB_PATH = os.environ.get("DATABASE_PATH")
elif os.path.exists("/data"):
    DB_PATH = "/data/alzzz_baru.db" 
else:
    DB_PATH = os.path.join(BASE_DIR, "alzzz.db") 
# ------------------------------------

UPLOAD_DIR = os.path.join(BASE_DIR, "static_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("ALZZZ_SECRET", "Admin1701")

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        display_name TEXT NOT NULL,
        photo TEXT,
        bio TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        entry_date TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        plan TEXT,
        result TEXT,
        notes TEXT,
        entry_date TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    
    try:
        conn.execute("ALTER TABLE users ADD COLUMN bio TEXT")
    except sqlite3.OperationalError:
        pass 

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", ("AlZzz",))
        if not cursor.fetchone():
            hashed_pw = generate_password_hash("Alfian170103")
            conn.execute("INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)",
                         ("AlZzz", hashed_pw, "admin", "AlZzz"))
    except Exception as e:
        pass

    conn.commit()
    conn.close()

init_db()

def current_user():
    if "user_id" not in session:
        return None
    return db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["role"] != "admin":
            flash("Halaman ini khusus admin.")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper

def auto_evaluate_trading(plan, result, notes):
    plan = plan or ""
    result = result or ""
    notes = notes or ""
    score = 0
    feedback = []
    
    if len(plan) < 10:
        feedback.append("Rencana trading terlalu singkat.")
    else:
        score += 20
        
    result_lower = result.lower()
    if "profit" in result_lower or "tp" in result_lower:
        score += 40
        feedback.append("Hasil positif, pertahankan!")
    elif "loss" in result_lower or "sl" in result_lower:
        score += 20
        feedback.append("Kerugian, evaluasi SL-mu.")
        
    if len(notes) > 20:
        score += 20
        feedback.append("Catatan bagus.")
    else:
        feedback.append("Catatan kurang mendalam.")
        
    if score >= 60: verdict = "SANGAT BAIK: Eksekusi terukur."
    elif score >= 30: verdict = "CUKUP BAIK: Perlu perbaikan kedisiplinan."
    else: verdict = "PERLU PERBAIKAN: Terkesan emosional."
        
    return f"{verdict} " + " ".join(feedback)

def auto_evaluate_finance(kind, category, amount, description):
    amount = float(amount)
    if kind == "Pengeluaran":
        if amount > 1000000:
            return "🚨 WADUH! Pengeluaran sangat besar. Pastikan ini kebutuhan mendesak, bukan sekadar keinginan!"
        elif category == "Makanan" or category == "Minuman":
            return "🍔 Kamu cukup sering jajan. Ingat, menabung itu penting untuk masa depan!"
        elif category == "Belanja":
            return "🛍️ Belanja lagi? Kontrol emosi dan cek keranjang belanjamu sebelum checkout!"
        else:
            return "📉 Pengeluaran tercatat. Pastikan pengeluaran ini memberi manfaat jangka panjang."
    else:
        if amount > 5000000:
            return "💰 Pemasukan besar! Segera alokasikan ke tabungan atau investasi sebelum habis untuk hal konsumtif."
        else:
            return "📈 Pemasukan bagus. Sisihkan minimal 10% untuk tabungan."

TEMPLATE = r"""
<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} • AlZzz Web</title>
<style>
:root{--bg:#080b18;--panel:#11182b;--line:#243454;--cyan:#42e8ff;--pink:#ff4fd8;--text:#eaf3ff;--muted:#9aabc5}

html, body {
    margin: 0; padding: 0; width: 100%; min-height: 100vh;
    background: radial-gradient(circle at top,#142444 0,#080b18 48%);
    color: var(--text);
    font: 15px Arial,sans-serif;
    overflow-x: hidden;
}

/* 1. Canvas di paling belakang */
#bg-graph {
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    z-index: 1; 
    pointer-events: none;
}

/* 2. Header di atas Canvas */
header {
    position: relative;
    z-index: 50; 
    padding: 15px 5%;
    border-bottom: 1px solid var(--line);
    display: flex; justify-content: space-between; align-items: center;
    background: #080b18;
}

/* 3. Main Container */
main {
    position: relative;
    z-index: 10; 
    max-width: 1050px;
    margin: 0 auto;
    padding: 28px 16px;
    box-sizing: border-box;
}

/* 4. Panel / Tabel 100% PEKAT (Solid) & RATA TENGAH */
.panel, .stat {
    background: #11182b; 
    border: 2px solid var(--line);
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 16px;
    margin-left: auto;  /* Memaksa Rata Kiri */
    margin-right: auto; /* Memaksa Rata Kanan */
    position: relative;
    z-index: 20;
    animation: neon-glow 4s linear infinite;
    box-shadow: 0 4px 15px rgba(0,0,0,0.8);
    box-sizing: border-box;
}

/* 5. Menu Dropdown 100% PEKAT */
.menu-dropdown {
    display: none;
    position: absolute;
    top: 60px; right: 5%;
    background: #11182b; 
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 10px;
    z-index: 999; 
    box-shadow: 0 10px 30px rgba(0,0,0,0.9);
    min-width: 200px;
}

@keyframes neon-glow {
    0%, 100% { box-shadow: 0 0 10px #42e8ff, inset 0 0 5px #42e8ff; border-color: #42e8ff; }
    25% { box-shadow: 0 0 10px #ff4fd8, inset 0 0 5px #ff4fd8; border-color: #ff4fd8; }
    50% { box-shadow: 0 0 10px #00ff88, inset 0 0 5px #00ff88; border-color: #00ff88; }
    75% { box-shadow: 0 0 10px #ffeb3b, inset 0 0 5px #ffeb3b; border-color: #ffeb3b; }
}

.header-left { display: flex; align-items: center; gap: 10px; }
.logo{font-weight:800;letter-spacing:2px;color:var(--cyan);text-shadow:0 0 12px #42e8ff66}
.hamburger{cursor:pointer;font-size:24px;color:var(--cyan);user-select:none}
.menu-dropdown a{display:block;padding:10px;color:var(--text);text-decoration:none;border-radius:8px}
.menu-dropdown a:hover{background:#243454;color:var(--cyan)}

h1,h2{margin-top:0}h1{font-size:25px}h2{font-size:19px;color:var(--cyan)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px; width: 100%;} 
.stat small{color:var(--muted)}.stat strong{display:block;font-size:23px;margin-top:8px}
input,select,textarea,button{font:inherit;border-radius:9px;padding:11px;width:100%;margin:6px 0;background:#0a1020;color:var(--text);border:1px solid #344665}
textarea{min-height:85px}button{background:linear-gradient(90deg,#087e9a,#673b91);border:0;font-weight:bold;cursor:pointer}button:hover{filter:brightness(1.2)}
label{display:block;color:var(--muted);margin-top:8px}.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}td,th{text-align:left;padding:10px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--cyan)}
.msg{padding:10px;background:#17334a;border-radius:8px;margin-bottom:12px; width: 100%; box-sizing: border-box;}.muted{color:var(--muted)}
.avatar-container{position:relative;display:inline-block}
.avatar{width:80px;height:80px;object-fit:cover;border-radius:50%;border:2px solid var(--cyan)}
.edit-icon{position:absolute;bottom:0;right:0;background:var(--cyan);border-radius:50%;width:25px;height:25px;display:flex;align-items:center;justify-content:center;color:#000;font-size:12px;cursor:pointer;text-decoration:none}
.edit-btn{background:none;border:1px solid var(--cyan);color:var(--cyan);padding:5px 10px;border-radius:5px;cursor:pointer;font-size:12px;width:auto;margin:0}
.btn-danger{background:#ff4f4f;color:white;padding:5px 10px;border-radius:5px;text-decoration:none;font-size:12px;}
footer{text-align:center;color:var(--muted);padding:30px; position: relative; z-index: 10;}

.music-btn {
    background: var(--pink); color: white; border: none; padding: 5px 10px; 
    border-radius: 20px; cursor: pointer; font-size: 12px; font-weight: bold; 
    box-shadow: 0 0 10px var(--pink); width: auto; margin: 0;
}

/* === TAMBAHAN CSS UNTUK LOGIN RATA TENGAH === */
main.auth-main {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 180px);
    padding-top: 20px;
    padding-bottom: 20px;
}
main.auth-main .panel {
    margin-left: auto;
    margin-right: auto;
    flex-shrink: 0;
}
main.auth-main .msg {
    max-width: 360px;
    width: 100%;
    text-align: center;
}
/* ============================================ */
</style></head><body>

<canvas id="bg-graph"></canvas>

<header>
  <div class="header-left">
      <div class="logo">👑 ALZZZ WEB</div>
      {% if user %}
      <button class="music-btn" onclick="togglePlay()" id="playBtn">🎵 Play DJ</button>
      {% endif %}
  </div>
  
  {% if user %}
  <div class="hamburger" onclick="var m = document.getElementById('myMenu'); m.style.display = (m.style.display === 'block') ? 'none' : 'block';">☰</div>
  <div id="myMenu" class="menu-dropdown">
      <a href="{{url_for('dashboard')}}">Dashboard</a>
      <a href="{{url_for('profile')}}">Profil</a>
      <a href="{{url_for('transactions')}}">Keuangan</a>
      <a href="{{url_for('journal_page')}}">Trading</a>
      <a href="{{url_for('evaluation_page')}}">Evaluasi (Otomatis)</a>
      {% if user.role=='admin' %}<a href="{{url_for('admin_page')}}">Admin Panel</a>{% endif %}
      <a href="{{url_for('logout')}}" style="color:var(--pink);">Keluar</a>
  </div>
  {% else %}
  <a href="{{url_for('login')}}" style="color:var(--cyan);text-decoration:none;">Login</a>
  {% endif %}
</header>

<!-- BAGIAN MAIN YANG SUDAH DIMODIFIKASI -->
<main{% if is_auth %} class="auth-main"{% endif %}>{% for m in get_flashed_messages() %}<div class="msg">{{m}}</div>{% endfor %}{{ body|safe }}</main>

<footer>AlZzz Web • Catat dan evaluasi keuangan dengan bijak</footer>

{% if user %}
<div id="yt-player" style="display:none;"></div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
    const canvas = document.getElementById('bg-graph');
    const ctx = canvas.getContext('2d');
    let width, height;
    let time = 0;
    const coins = [];

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resize);
    resize();

    for (let i = 0; i < 30; i++) {
        coins.push({
            x: Math.random() * window.innerWidth,
            y: Math.random() * window.innerHeight,
            speed: 1 + Math.random() * 2,
            size: 20 + Math.random() * 30,
            opacity: 0.1 + Math.random() * 0.3
        });
    }

    function draw() {
        ctx.clearRect(0, 0, width, height);
        time += 0.02; 

        const colors = ['rgba(66, 232, 255,', 'rgba(255, 79, 216,'];
        for(let j=0; j<2; j++) {
            ctx.beginPath();
            ctx.strokeStyle = colors[j] + ' 0.3)'; 
            ctx.lineWidth = 2;

            let points = [];
            for(let x=0; x <= width; x+=10) {
                let y = height/2 
                      + Math.sin((x * 0.005) + time + j) * 100 
                      + Math.cos((x * 0.01) + (time * 1.5) + j) * 50;
                points.push({x: x, y: y});
            }

            points.forEach((p, i) => {
                if(i===0) ctx.moveTo(p.x, p.y);
                else ctx.lineTo(p.x, p.y);
            });
            ctx.stroke();

            ctx.lineTo(width, height);
            ctx.lineTo(0, height);
            ctx.closePath();
            let gradient = ctx.createLinearGradient(0, 0, 0, height);
            gradient.addColorStop(0, colors[j] + ' 0.1)');
            gradient.addColorStop(1, colors[j] + ' 0)');
            ctx.fillStyle = gradient;
            ctx.fill();
        }

        coins.forEach(c => {
            ctx.font = "bold " + c.size + "px Arial";
            ctx.fillStyle = `rgba(247, 147, 26, ${c.opacity})`; 
            ctx.textAlign = "center";
            ctx.fillText("₿", c.x, c.y);

            c.y -= c.speed; 
            if (c.y < -50) {
                c.y = height + 50;
                c.x = Math.random() * width;
            }
        });

        requestAnimationFrame(draw);
    }
    draw();

    var player;
    var isPlaying = localStorage.getItem('musicPlaying') === 'true';

    function onYouTubeIframeAPIReady() {
        var btn = document.getElementById("playBtn");
        if(btn) btn.innerHTML = isPlaying ? "⏸️ Pause DJ" : "🎵 Play DJ";

        player = new YT.Player('yt-player', {
            height: '0', width: '0',
            videoId: 'sQn6XwEG13Q', 
            playerVars: { 'autoplay': 0, 'loop': 1, 'playlist': 'sQn6XwEG13Q' },
            events: {
                'onReady': (event) => {
                    if (isPlaying) {
                        let time = parseFloat(localStorage.getItem('musicTime') || '0');
                        event.target.seekTo(time);
                        event.target.playVideo();
                    }
                }
            }
        });
    }

    function togglePlay() {
        if (!player) return;
        if (isPlaying) {
            player.pauseVideo();
            isPlaying = false;
            localStorage.setItem('musicPlaying', 'false');
            document.getElementById('playBtn').innerHTML = "🎵 Play DJ";
        } else {
            player.playVideo();
            isPlaying = true;
            localStorage.setItem('musicPlaying', 'true');
            document.getElementById('playBtn').innerHTML = "⏸️ Pause DJ";
        }
    }

    document.body.addEventListener('click', function() {
        if (isPlaying && player && player.getPlayerState && player.getPlayerState() !== 1) {
            player.playVideo();
        }
    });

    setInterval(() => {
        if (isPlaying && player && player.getCurrentTime) {
            localStorage.setItem('musicTime', player.getCurrentTime());
        }
    }, 1000);
</script>
{% endif %}

</body></html>
"""

# === FUNGSI PAGE YANG SUDAH DIMODIFIKASI ===
def page(title, body, **context):
    u = current_user()
    return render_template_string(
        TEMPLATE,
        title=title,
        body=render_template_string(body, **context),
        user=u,
        is_auth=(u is None)
    )

@app.route("/")
def home():
    return redirect(url_for("dashboard") if current_user() else url_for("setup" if db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0 else "login"))

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if db().execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return redirect(url_for("login"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display = request.form.get("display_name", "").strip() or username
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 12:
            flash("Username minimal 3 karakter dan kata sandi minimal 12 karakter.")
        else:
            db().execute("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                         (username, generate_password_hash(password), "admin", display))
            db().commit()
            flash("Admin berhasil dibuat. Silakan login.")
            return redirect(url_for("login"))
    
    body = """<div class="panel" style="max-width:320px; width:100%;"><h1>Pengaturan awal</h1><p class="muted">Buat akun admin pertama.</p>
    <form method="post"><label>Username admin</label><input name="username" required minlength="3">
    <label>Nama tampilan</label><input name="display_name">
    <label>Kata sandi (minimal 12 karakter)</label><input type="password" name="password" required minlength="12">
    <button>Buat admin</button></form></div>"""
    return page("Setup", body)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["just_logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Username atau kata sandi tidak cocok.")
    
    body = """<div class="panel" style="max-width:280px; width:100%;"><h1 style="text-align:center;">LOGIN</h1>
    <form method="post"><label>Username</label><input name="username" required>
    <label>Kata sandi</label><input type="password" name="password" required>
    <button>Masuk</button></form>
    <p style="text-align:center; margin-top:15px; font-size:12px;">Belum punya akun? <a href="{{url_for('register')}}" style="color:var(--cyan); text-decoration:none;">Daftar di sini</a></p>
    </div>"""
    return page("Login", body)

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display = request.form.get("display_name", "").strip() or username
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 12:
            flash("Username minimal 3 karakter dan kata sandi minimal 12 karakter.")
        else:
            try:
                db().execute("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                             (username, generate_password_hash(password), "member", display))
                db().commit()
                flash("Pendaftaran berhasil! Silakan login.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username sudah digunakan. Silakan pilih yang lain.")
                
    body = """<div class="panel" style="max-width:300px; width:100%;"><h1 style="text-align:center;">DAFTAR AKUN</h1>
    <p class="muted" style="text-align:center; font-size:12px;">Buat akun untuk mulai mencatat keuanganmu.</p>
    <form method="post">
        <label>Username</label><input name="username" required minlength="3">
        <label>Nama Tampilan (Opsional)</label><input name="display_name">
        <label>Kata sandi (minimal 12 karakter)</label><input type="password" name="password" required minlength="12">
        <button>Daftar Sekarang</button>
    </form></div>"""
    return page("Register", body)

# --- ROUTE SISA YANG SEBELUMNYA TERPOTONG (Dibuat standar agar web berjalan) ---

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    body = f"""<div class="panel" style="max-width:600px; width:100%;">
    <h1>Selamat datang, {user['display_name']}!</h1>
    <p class="muted">Ini adalah halaman dashboard kamu. Gunakan menu di kanan atas untuk mulai mencatat keuangan dan trading.</p>
    <div class="grid" style="margin-top:20px;">
        <div class="stat" style="margin:0;"><small>Status Akun</small><strong style="color:var(--cyan);">{user['role'].upper()}</strong></div>
    </div>
    </div>"""
    return page("Dashboard", body)

@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    if request.method == "POST":
        kind = request.form.get("kind")
        category = request.form.get("category")
        amount = request.form.get("amount", 0)
        description = request.form.get("description", "")
        advice = auto_evaluate_finance(kind, category, amount, description)
        
        db().execute("INSERT INTO transactions (user_id, kind, category, amount, description, entry_date) VALUES (?, ?, ?, ?, ?, ?)",
                     (session["user_id"], kind, category, amount, description + " | " + advice, date.today().isoformat()))
        db().commit()
        flash("Transaksi berhasil dicatat!")
        return redirect(url_for("transactions"))

    txs = db().execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    rows = "".join([f"<tr><td>{t['entry_date']}</td><td>{t['kind']}</td><td>{t['category']}</td><td>{t['amount']}</td><td>{t['description']}</td></tr>" for t in txs])
    
    body = f"""<div class="panel" style="max-width:800px; width:100%;">
    <h2>Catatan Keuangan</h2>
    <form method="post" class="row">
        <select name="kind"><option>Pemasukan</option><option>Pengeluaran</option></select>
        <input name="category" placeholder="Kategori (cth: Makanan)" required>
        <input type="number" name="amount" placeholder="Jumlah (Rp)" required>
        <input name="description" placeholder="Keterangan">
        <button>Tambah</button>
    </form>
    <div style="margin-top:20px;">
        <table><tr><th>Tanggal</th><th>Jenis</th><th>Kategori</th><th>Jumlah</th><th>Keterangan</th></tr>{rows}</table>
    </div>
    </div>"""
    return page("Keuangan", body)

@app.route("/journal", methods=["GET", "POST"])
@login_required
def journal_page():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        plan = request.form.get("plan")
        result = request.form.get("result")
        notes = request.form.get("notes")
        advice = auto_evaluate_trading(plan, result, notes)
        
        db().execute("INSERT INTO journal (user_id, symbol, plan, result, notes, entry_date) VALUES (?, ?, ?, ?, ?, ?)",
                     (session["user_id"], symbol, plan, result, notes + " | " + advice, date.today().isoformat()))
        db().commit()
        flash("Jurnal trading berhasil ditambahkan!")
        return redirect(url_for("journal_page"))

    js = db().execute("SELECT * FROM journal WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    rows = "".join([f"<tr><td>{j['entry_date']}</td><td>{j['symbol']}</td><td>{j['plan']}</td><td>{j['result']}</td></tr>" for j in js])

    body = f"""<div class="panel" style="max-width:800px; width:100%;">
    <h2>Jurnal Trading</h2>
    <form method="post" class="row">
        <input name="symbol" placeholder="Pair (cth: BTCUSD)" required>
        <input name="plan" placeholder="Rencana" required>
        <input name="result" placeholder="Hasil (Profit/Loss)">
        <input name="notes" placeholder="Catatan">
        <button>Simpan</button>
    </form>
    <div style="margin-top:20px;">
        <table><tr><th>Tanggal</th><th>Pair</th><th>Plan</th><th>Hasil</th></tr>{rows}</table>
    </div>
    </div>"""
    return page("Trading", body)

@app.route("/evaluation")
@login_required
def evaluation_page():
    # Sekadar menampilkan pesan karena logika evaluasi sudah dimasukkan ke note saat create
    body = """<div class="panel" style="max-width:600px; width:100%;">
    <h2>Evaluasi Otomatis</h2>
    <p class="muted">Sistem telah memberikan evaluasi otomatis ke dalam catatan Anda di halaman Keuangan dan Trading. AI akan menilai kedisiplinan dan pengeluaran Anda berdasarkan input.</p>
    </div>"""
    return page("Evaluasi", body)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        display = request.form.get("display_name")
        bio = request.form.get("bio")
        db().execute("UPDATE users SET display_name=?, bio=? WHERE id=?", (display, bio, user["id"]))
        db().commit()
        flash("Profil diperbarui!")
        return redirect(url_for("profile"))
        
    body = f"""<div class="panel" style="max-width:400px; width:100%;">
    <h2>Profil Pengguna</h2>
    <form method="post">
        <label>Nama Tampilan</label><input name="display_name" value="{user['display_name']}">
        <label>Bio</label><textarea name="bio">{user['bio'] or ''}</textarea>
        <button>Simpan Perubahan</button>
    </form>
    </div>"""
    return page("Profil", body)

@app.route("/admin")
@admin_required
def admin_page():
    users = db().execute("SELECT * FROM users").fetchall()
    rows = "".join([f"<tr><td>{u['id']}</td><td>{u['username']}</td><td>{u['role']}</td></tr>" for u in users])
    body = f"""<div class="panel" style="max-width:600px; width:100%;">
    <h2>Admin Panel</h2>
    <table><tr><th>ID</th><th>Username</th><th>Role</th></tr>{rows}</table>
    </div>"""
    return page("Admin", body)

@app.errorhandler(413)
def too_large(e):
    flash("File terlalu besar! Maksimal 2MB.")
    return redirect(url_for("profile"))

if __name__ == "__main__":
    app.run(debug=True)
