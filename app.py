import os
import sqlite3
from functools import wraps
from datetime import date, datetime
from flask import Flask, g, request, redirect, url_for, session, flash, render_template_string, get_flashed_messages
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

/* PERBAIKAN BACKGROUND & LAYER */
html {
    background: radial-gradient(circle at top,#142444 0,#080b18 48%);
    height: 100%;
}
body {
    margin: 0;
    background: transparent; /* Dibuat transparan agar canvas terlihat */
    color: var(--text);
    font: 15px Arial,sans-serif;
    overflow-x: hidden;
}

/* LAYER KONTEN DI ATAS CANVAS */
header, main, footer {
    position: relative;
    z-index: 10; 
}

/* PANEL & TABEL 100% SOLID (PEKAT) */
.panel, .stat {
    background: #11182b; /* Warna solid, tidak tembus pandang */
    border: 2px solid var(--line);
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 16px;
    animation: neon-glow 4s linear infinite;
    box-shadow: 0 4px 15px rgba(0,0,0,0.8); /* Bayangan tebal agar terpisah dari background */
}

header{padding:15px 5%;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;align-items:center; background: #080b18cc; backdrop-filter: blur(5px);}
.header-left { display: flex; align-items: center; gap: 10px; }
.logo{font-weight:800;letter-spacing:2px;color:var(--cyan);text-shadow:0 0 12px #42e8ff66}
.hamburger{cursor:pointer;font-size:24px;color:var(--cyan);user-select:none}
.menu-dropdown{display:none;position:absolute;top:60px;right:5%;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px;z-index:100;box-shadow:0 10px 30px #0008;min-width:200px}
.menu-dropdown a{display:block;padding:10px;color:var(--text);text-decoration:none;border-radius:8px}
.menu-dropdown a:hover{background:#243454;color:var(--cyan)}
main{max-width:1050px;margin:28px auto;padding:0 16px;}
h1,h2{margin-top:0}h1{font-size:25px}h2{font-size:19px;color:var(--cyan)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}.stat small{color:var(--muted)}.stat strong{display:block;font-size:23px;margin-top:8px}
input,select,textarea,button{font:inherit;border-radius:9px;padding:11px;width:100%;margin:6px 0;background:#0a1020;color:var(--text);border:1px solid #344665}
textarea{min-height:85px}button{background:linear-gradient(90deg,#087e9a,#673b91);border:0;font-weight:bold;cursor:pointer}button:hover{filter:brightness(1.2)}
label{display:block;color:var(--muted);margin-top:8px}.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}td,th{text-align:left;padding:10px;border-bottom:1px solid var(--line);white-space:nowrap}th{color:var(--cyan)}
.msg{padding:10px;background:#17334a;border-radius:8px;margin-bottom:12px}.muted{color:var(--muted)}
.avatar-container{position:relative;display:inline-block}
.avatar{width:80px;height:80px;object-fit:cover;border-radius:50%;border:2px solid var(--cyan)}
.edit-icon{position:absolute;bottom:0;right:0;background:var(--cyan);border-radius:50%;width:25px;height:25px;display:flex;align-items:center;justify-content:center;color:#000;font-size:12px;cursor:pointer;text-decoration:none}
.edit-btn{background:none;border:1px solid var(--cyan);color:var(--cyan);padding:5px 10px;border-radius:5px;cursor:pointer;font-size:12px;width:auto;margin:0}
.btn-danger{background:#ff4f4f;color:white;padding:5px 10px;border-radius:5px;text-decoration:none;font-size:12px;}
footer{text-align:center;color:var(--muted);padding:30px;}

@keyframes neon-glow {
    0%, 100% { box-shadow: 0 0 10px #42e8ff, inset 0 0 5px #42e8ff; border-color: #42e8ff; }
    25% { box-shadow: 0 0 10px #ff4fd8, inset 0 0 5px #ff4fd8; border-color: #ff4fd8; }
    50% { box-shadow: 0 0 10px #00ff88, inset 0 0 5px #00ff88; border-color: #00ff88; }
    75% { box-shadow: 0 0 10px #ffeb3b, inset 0 0 5px #ffeb3b; border-color: #ffeb3b; }
}

.music-btn {
    background: var(--pink); color: white; border: none; padding: 5px 10px; 
    border-radius: 20px; cursor: pointer; font-size: 12px; font-weight: bold; 
    box-shadow: 0 0 10px var(--pink); width: auto; margin: 0;
}

/* CANVAS DIPOSISIKAN DI PALING BELAKANG */
#bg-graph {
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 100vh;
    z-index: 1; 
    pointer-events: none;
}
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
<main>{% for m in get_flashed_messages() %}<div class="msg">{{m}}</div>{% endfor %}{{ body|safe }}</main>
<footer>AlZzz Web • Catat dan evaluasi keuangan dengan bijak</footer>

{% if user %}
<div id="yt-player" style="display:none;"></div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
    // --- GRAFIK AREA & BITCOIN BERGERAK ---
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

    // Inisialisasi Koin Bitcoin (lebih banyak dan lebih besar)
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

        // 1. Gambar Gelombang
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

        // 2. Gambar Koin Bitcoin
        coins.forEach(c => {
            ctx.font = "bold " + c.size + "px Arial";
            ctx.fillStyle = `rgba(247, 147, 26, ${c.opacity})`; // Warna Emas/Bitcoin
            ctx.textAlign = "center";
            ctx.fillText("₿", c.x, c.y);

            c.y -= c.speed; // Naik ke atas
            
            if (c.y < -50) {
                c.y = height + 50;
                c.x = Math.random() * width;
            }
        });

        requestAnimationFrame(draw);
    }
    draw();

    // --- SCRIPT MUSIK YOUTUBE (PERSISTEN) ---
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
            document.getElementById("playBtn").innerHTML = "🎵 Play DJ";
        } else {
            player.playVideo();
            isPlaying = true;
            localStorage.setItem('musicPlaying', 'true');
            document.getElementById("playBtn").innerHTML = "⏸️ Pause DJ";
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

def page(title, body, **context):
    return render_template_string(TEMPLATE, title=title, body=render_template_string(body, **context), user=current_user())

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
    body = """<div class="panel"><h1>Pengaturan awal AlZzz Web</h1><p class="muted">Buat akun admin pertama.</p>
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
            return redirect(url_for("dashboard"))
        flash("Username atau kata sandi tidak cocok.")
    body = """<div class="panel" style="max-width:350px;margin:auto;padding:15px;"><h1 style="text-align:center;">LOGIN</h1>
    <form method="post"><label>Username</label><input name="username" required>
    <label>Kata sandi</label><input type="password" name="password" required>
    <button>Masuk</button></form>
    <p style="text-align:center; margin-top:15px; font-size:14px;">Belum punya akun? <a href="{{url_for('register')}}" style="color:var(--cyan); text-decoration:none;">Daftar di sini</a></p>
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
                
    body = """<div class="panel" style="max-width:380px;margin:auto;padding:15px;"><h1 style="text-align:center;">DAFTAR AKUN</h1>
    <p class="muted" style="text-align:center;">Buat akun untuk mulai mencatat keuanganmu.</p>
    <form method="post">
        <label>Username</label><input name="username" required minlength="3">
        <label>Nama Tampilan (Opsional)</label><input name="display_name">
        <label>Kata sandi (minimal 12 karakter)</label><input type="password" name="password" required minlength="12">
        <button>Daftar Sekarang</button>
    </form>
    <p style="text-align:center; margin-top:15px; font-size:14px;">Sudah punya akun? <a href="{{url_for('login')}}" style="color:var(--cyan); text-decoration:none;">Login di sini</a></p>
    </div>"""
    return page("Daftar", body)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    month = date.today().strftime("%Y-%m")
    args = (user["id"], month + "%")
    totals = db().execute("""SELECT kind,COALESCE(SUM(amount),0) total FROM transactions
        WHERE user_id=? AND entry_date LIKE ? GROUP BY kind""", args).fetchall()
    income = next((r["total"] for r in totals if r["kind"] == "Pemasukan"), 0)
    expense = next((r["total"] for r in totals if r["kind"] == "Pengeluaran"), 0)
    recent = db().execute("SELECT * FROM transactions WHERE user_id=? ORDER BY entry_date DESC,id DESC LIMIT 8",(user["id"],)).fetchall()
    
    body = """<h1>Dashboard</h1><p class="muted">Halo, {{user.display_name}} • Ringkasan bulan {{month}}</p>
    <div class="grid"><div class="stat"><small>Total pemasukan</small><strong>Rp {{'{:,.0f}'.format(income)}}</strong></div>
    <div class="stat"><small>Total pengeluaran</small><strong>Rp {{'{:,.0f}'.format(expense)}}</strong></div>
    <div class="stat"><small>Selisih</small><strong>Rp {{'{:,.0f}'.format(income-expense)}}</strong></div></div>
    <div class="panel"><h2>Transaksi terbaru</h2>{% if recent %}<table><tr><th>Tanggal</th><th>Jenis</th><th>Kategori</th><th>Jumlah</th></tr>
    {% for x in recent %}<tr><td>{{x.entry_date}}</td><td>{{x.kind}}</td><td>{{x.category}}</td><td>Rp {{'{:,.0f}'.format(x.amount)}}</td></tr>{% endfor %}</table>{% else %}<p class="muted">Belum ada transaksi.</p>{% endif %}</div>
    <div class="panel"><h2>Grafik bulan ini</h2><canvas id="chart" height="110"></canvas></div>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
    new Chart(document.getElementById('chart'),{type:'bar',data:{labels:['Pemasukan','Pengeluaran'],datasets:[{label:'Rupiah',data:[{{income}},{{expense}}]}]},options:{responsive:true,plugins:{legend:{display:false}}}});
    
    window.onload = function() {
        if ('speechSynthesis' in window) {
            var namaUser = "{{ user.display_name|safe }}";
            var pesan = "Selamat datang bos " + namaUser + ", semoga rezekimu lancar dan berkah hari ini";
            var speech = new SpeechSynthesisUtterance(pesan);
            speech.lang = 'id-ID'; speech.rate = 0.9; speech.pitch = 1; 
            setTimeout(function() { window.speechSynthesis.speak(speech); }, 500);
        }
    };
    </script>"""
    return page("Dashboard", body, user=user, month=month, income=income, expense=expense, recent=recent)

@app.route("/transactions", methods=["GET", "POST"])
@app.route("/transactions/edit/<int:id>", methods=["GET", "POST"])
@login_required
def transactions(id=None):
    user = current_user()
    edit_data = None
    if id:
        edit_data = db().execute("SELECT * FROM transactions WHERE id=? AND user_id=?", (id, user["id"])).fetchone()
        if not edit_data:
            flash("Transaksi tidak ditemukan.")
            return redirect(url_for("transactions"))

    if request.method == "POST":
        kind = request.form.get("kind")
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        try:
            amount = float(request.form.get("amount", "0"))
            entry_date = request.form.get("entry_date") or date.today().isoformat()
            if kind not in ("Pemasukan", "Pengeluaran") or not category or amount <= 0:
                raise ValueError()
            
            if id: 
                db().execute("UPDATE transactions SET kind=?, category=?, amount=?, description=?, entry_date=? WHERE id=? AND user_id=?",
                             (kind, category, amount, description, entry_date, id, user["id"]))
                flash("Transaksi berhasil diperbarui.")
            else: 
                db().execute("INSERT INTO transactions(user_id,kind,category,amount,description,entry_date) VALUES(?,?,?,?,?,?)",
                             (user["id"], kind, category, amount, description, entry_date))
                flash("Transaksi berhasil disimpan.")
            db().commit()
            return redirect(url_for("transactions"))
        except ValueError:
            flash("Periksa jenis, kategori, tanggal, dan jumlah transaksi.")
            
    rows = db().execute("SELECT * FROM transactions WHERE user_id=? ORDER BY entry_date DESC,id DESC",(user["id"],)).fetchall()
    
    form_title = "Edit Transaksi" if edit_data else "Catat Transaksi"
    val_kind = edit_data['kind'] if edit_data else 'Pemasukan'
    val_cat = edit_data['category'] if edit_data else 'Makanan'
    val_amt = edit_data['amount'] if edit_data else ''
    val_date = edit_data['entry_date'] if edit_data else date.today().isoformat()
    val_desc = edit_data['description'] if edit_data else ''
    form_action = url_for('transactions', id=id) if id else url_for('transactions')

    body = """<div class="panel"><h1>{{form_title}}</h1><form method="post" action="{{form_action}}"><div class="row">
    <div><label>Jenis</label><select name="kind">
        <option {% if val_kind=="Pemasukan" %}selected{% endif %}>Pemasukan</option>
        <option {% if val_kind=="Pengeluaran" %}selected{% endif %}>Pengeluaran</option>
    </select></div>
    <div><label>Kategori</label><select name="category" id="category-select">
        <option>Makanan</option><option>Minuman</option><option>Gaji</option><option>Transportasi</option><option>Belanja</option><option>Tabungan</option><option>Lainnya</option>
    </select></div>
    <div><label>Jumlah (Rp)</label><input type="number" name="amount" min="1" step="1" value="{{val_amt}}" required></div>
    <div><label>Tanggal</label><input type="date" name="entry_date" value="{{val_date}}" required></div></div>
    <label>Keterangan</label><textarea name="description">{{val_desc}}</textarea><button>Simpan</button></form></div>
    
    <div class="panel"><h2>Riwayat Keuangan</h2>{% if rows %}<table><tr><th>Tanggal</th><th>Jenis</th><th>Kategori</th><th>Jumlah</th><th>Aksi</th></tr>
    {% for x in rows %}<tr><td>{{x.entry_date}}</td><td>{{x.kind}}</td><td>{{x.category}}</td><td>Rp {{'{:,.0f}'.format(x.amount)}}</td>
    <td><a href="{{url_for('transactions', id=x.id)}}" class="edit-btn">✏️ Edit</a></td></tr>{% endfor %}</table>{% else %}<p class="muted">Belum ada data.</p>{% endif %}</div>"""
    
    script = f"""<script>
    document.getElementById('category-select').value = "{val_cat}";
    </script>"""
    
    return page("Transaksi", body + script, rows=rows, form_title=form_title, form_action=form_action,
                val_kind=val_kind, val_amt=val_amt, val_date=val_date, val_desc=val_desc)

@app.route("/journal", methods=["GET", "POST"])
@login_required
def journal_page():
    user = current_user()
    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip()
        if symbol:
            db().execute("INSERT INTO journal(user_id,symbol,plan,result,notes,entry_date) VALUES(?,?,?,?,?,?)",
                         (user["id"], symbol, request.form.get("plan",""), request.form.get("result",""),
                          request.form.get("notes",""), request.form.get("entry_date") or date.today().isoformat()))
            db().commit()
            flash("Catatan jurnal tersimpan.")
            return redirect(url_for("journal_page"))
        flash("Nama aset/instrumen wajib diisi.")
    rows = db().execute("SELECT * FROM journal WHERE user_id=? ORDER BY entry_date DESC,id DESC",(user["id"],)).fetchall()
    body = """<div class="panel"><h1>Jurnal trading</h1><p class="muted">Gunakan untuk mencatat rencana dan evaluasi.</p>
    <form method="post"><label>Aset / instrumen</label><input name="symbol" required>
    <label>Rencana</label><textarea name="plan"></textarea><label>Hasil</label><input name="result">
    <label>Catatan</label><textarea name="notes"></textarea><label>Tanggal</label><input type="date" name="entry_date" value="{{today}}">
    <button>Simpan jurnal</button></form></div><div class="panel"><h2>Riwayat jurnal</h2>
    {% for x in rows %}<div style="border-bottom:1px solid #243454;padding:10px 0"><b>{{x.entry_date}} • {{x.symbol}}</b><p>{{x.plan}}</p><p>{{x.result}}</p><p class="muted">{{x.notes}}</p></div>{% else %}<p class="muted">Belum ada catatan jurnal.</p>{% endfor %}</div>"""
    return page("Jurnal", body, rows=rows, today=date.today().isoformat())

@app.route("/evaluation")
@login_required
def evaluation_page():
    user = current_user()
    journals = db().execute("SELECT * FROM journal WHERE user_id=? ORDER BY entry_date DESC,id DESC",(user["id"],)).fetchall()
    transactions = db().execute("SELECT * FROM transactions WHERE user_id=? ORDER BY entry_date DESC,id DESC LIMIT 20",(user["id"],)).fetchall()
    
    body = """<div class="panel"><h1>Evaluasi Jurnal Trading</h1><p class="muted">Sistem menganalisis cara tradingmu.</p>"""
    if not journals:
        body += "<p>Belum ada data trading.</p></div>"
    else:
        body += """<table><tr><th>Tanggal</th><th>Aset</th><th>Hasil Evaluasi Sistem</th></tr>"""
        for x in journals:
            eval_text = auto_evaluate_trading(x["plan"], x["result"], x["notes"])
            body += f"""<tr><td>{x['entry_date']}</td><td><b>{x['symbol']}</b></td><td style="white-space:normal; max-width:400px;">{eval_text}</td></tr>"""
        body += "</table></div>"

    body += """<div class="panel" style="border-color: var(--pink);"><h1>Evaluasi Keuangan (Baru!)</h1><p class="muted">Sistem menganalisis polamu dalam membelanjakan uang.</p>"""
    if not transactions:
        body += "<p>Belum ada data keuangan.</p></div>"
    else:
        body += """<table><tr><th>Tanggal</th><th>Kategori</th><th>Jumlah</th><th>Komentar Sistem</th></tr>"""
        for x in transactions:
            eval_fin = auto_evaluate_finance(x["kind"], x["category"], x["amount"], x["description"])
            body += f"""<tr><td>{x['entry_date']}</td><td>{x['category']}</td><td>Rp {x['amount']:,.0f}</td><td style="white-space:normal; max-width:300px; color:var(--cyan);">{eval_fin}</td></tr>"""
        body += "</table></div>"
    
    return page("Evaluasi", body)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_bio":
            db().execute("UPDATE users SET bio=? WHERE id=?", (request.form.get("bio",""), user["id"]))
            db().commit()
            flash("Bio diperbarui.")
            
        elif action == "update_credentials":
            display = request.form.get("display_name", "").strip() or user["username"]
            db().execute("UPDATE users SET display_name=? WHERE id=?", (display, user["id"]))
            new_password = request.form.get("new_password", "")
            if new_password:
                if len(new_password) < 12:
                    flash("Kata sandi baru minimal 12 karakter.")
                    return redirect(url_for("profile"))
                db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), user["id"]))
            db().commit()
            flash("Nama/Password diperbarui.")
            
        elif action == "update_photo":
            file = request.files.get("photo")
            if file and file.filename:
                ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
                if ext in ALLOWED_EXTENSIONS:
                    filename = secure_filename(f"user_{user['id']}_{int(datetime.now().timestamp())}.{ext}")
                    file.save(os.path.join(UPLOAD_DIR, filename))
                    db().execute("UPDATE users SET photo=? WHERE id=?", (filename, user["id"]))
                    db().commit()
                    flash("Foto profil diperbarui.")
                else:
                    flash("Format foto tidak didukung.")
        return redirect(url_for("profile"))
        
    body = """
    <div class="panel" style="text-align:center; position:relative;">
        <div class="avatar-container">
            {% if user.photo %}
                <img class="avatar" src="/static_uploads/{{user.photo}}" alt="Foto">
            {% else %}
                <div class="avatar" style="background:#243454; display:flex; align-items:center; justify-content:center; margin:0 auto;">👤</div>
            {% endif %}
            <a href="#" class="edit-icon" onclick="document.getElementById('photoForm').style.display='block';">✏️</a>
        </div>
        
        <h1 style="margin-top:10px;">{{user.display_name}} <a href="#" style="font-size:14px;text-decoration:none;" onclick="document.getElementById('credForm').style.display='block';">✏️</a></h1>
        <p class="muted" style="margin-bottom:15px;">@{{user.username}}</p>
        
        <div style="background:#0a1020;padding:15px;border-radius:10px;border:1px solid #344665;text-align:left;">
            <b>Bio:</b> <span class="muted">{{user.bio if user.bio else 'Belum ada bio.'}}</span> 
            <a href="#" style="font-size:12px;text-decoration:none;float:right;" onclick="document.getElementById('bioForm').style.display='block';">✏️ Edit</a>
        </div>
    </div>

    <div id="photoForm" class="panel" style="display:none;">
        <h2>Ubah Foto Profil</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="hidden" name="action" value="update_photo">
            <input type="file" name="photo" accept=".png,.jpg,.jpeg,.webp" required>
            <button>Upload Foto</button>
        </form>
    </div>

    <div id="bioForm" class="panel" style="display:none;">
        <h2>Ubah Bio</h2>
        <form method="post">
            <input type="hidden" name="action" value="update_bio">
            <textarea name="bio" placeholder="Tulis biografi singkat...">{{user.bio if user.bio else ''}}</textarea>
            <button>Simpan Bio</button>
        </form>
    </div>

    <div id="credForm" class="panel" style="display:none;">
        <h2>Ubah Nama & Sandi</h2>
        <form method="post">
            <input type="hidden" name="action" value="update_credentials">
            <label>Nama Tampilan</label><input name="display_name" value="{{user.display_name}}">
            <label>Kata Sandi Baru (Kosongkan jika tidak diganti)</label><input type="password" name="new_password">
            <button>Simpan Perubahan</button>
        </form>
    </div>
    """
    return page("Profil", body, user=user)

@app.route("/static_uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/admin", methods=["GET", "POST"])
@app.route("/admin/delete/<int:id>", methods=["POST"])
@admin_required
def admin_page(id=None):
    if id:
        if id != current_user()["id"]:
            db().execute("DELETE FROM users WHERE id=?", (id,))
            db().commit()
            flash("Member berhasil dihapus.")
        else:
            flash("Anda tidak bisa menghapus akun Anda sendiri.")
        return redirect(url_for("admin_page"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        display = request.form.get("display_name", "").strip() or username
        if len(username) < 3 or len(password) < 12:
            flash("Username minimal 3 karakter dan sandi minimal 12 karakter.")
        else:
            try:
                db().execute("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                             (username, generate_password_hash(password), "member", display))
                db().commit()
                flash("Akun anggota berhasil dibuat.")
            except sqlite3.IntegrityError:
                flash("Username sudah digunakan.")
                
    users = db().execute("SELECT id,username,display_name,role FROM users ORDER BY id").fetchall()
    body = """<div class="panel"><h1>Admin Panel</h1><form method="post"><label>Username anggota</label><input name="username" required minlength="3">
    <label>Nama tampilan</label><input name="display_name"><label>Sandi (minimal 12 karakter)</label><input name="password" type="password" required minlength="12">
    <button>Buat akun anggota</button></form></div>
    
    <div class="panel"><h2>Daftar Akun</h2><table><tr><th>Username</th><th>Nama</th><th>Peran</th><th>Aksi</th></tr>
    {% for x in users %}<tr><td>{{x.username}}</td><td>{{x.display_name}}</td><td>{{x.role}}</td>
    <td>{% if x.role != 'admin' %}
        <form method="post" action="{{url_for('admin_page', id=x.id)}}" onsubmit="return confirm('Hapus member ini?');" style="margin:0;">
            <button class="btn-danger" type="submit">Hapus</button>
        </form>
    {% else %}-{% endif %}</td></tr>{% endfor %}</table></div>"""
    return page("Admin", body, users=users)

@app.errorhandler(413)
def too_large(_error):
    flash("Ukuran file terlalu besar. Maksimal 2 MB.")
    return redirect(url_for("profile"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
