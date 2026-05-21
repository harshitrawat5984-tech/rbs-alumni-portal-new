import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'rbs_mtc_secret_key_for_ayush_project'
DATABASE = 'database.db'

# ==========================================
# DATABASE SETTING & RELATIONAL MATRIX
# ==========================================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Admin', 'Alumni', 'Student')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                graduation_year INTEGER,
                current_company TEXT,
                skill_tags TEXT,
                FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Job_Postings (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                posted_by INTEGER NOT NULL,
                job_title TEXT NOT NULL,
                company_name TEXT NOT NULL,
                job_description TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                FOREIGN KEY (posted_by) REFERENCES Users(user_id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Users")
        if cursor.fetchone()[0] == 0:
            mock_pass = generate_password_hash("password123")
            
            # Seed 1: Verified Alumni 1
            cursor.execute("INSERT INTO Users (email, password_hash, role) VALUES (?, ?, ?)", ("amit.sharma@gmail.com", mock_pass, "Alumni"))
            alumni_id = cursor.lastrowid
            cursor.execute("INSERT INTO Profiles (user_id, full_name, graduation_year, current_company, skill_tags) VALUES (?, ?, ?, ?, ?)",
                           (alumni_id, "Amit Sharma", 2024, "Google", "Java, Spring Boot, System Design"))
            
            # Seed 2: Verified Alumni 2
            cursor.execute("INSERT INTO Users (email, password_hash, role) VALUES (?, ?, ?)", ("priya.rawat@outlook.com", mock_pass, "Alumni"))
            alumni2_id = cursor.lastrowid
            cursor.execute("INSERT INTO Profiles (user_id, full_name, graduation_year, current_company, skill_tags) VALUES (?, ?, ?, ?, ?)",
                           (alumni2_id, "Priya Rawat", 2023, "Microsoft", "React, Node.js, Cloud Architectures"))

            # Seed 3: Student (Ayush Rawat)
            cursor.execute("INSERT INTO Users (email, password_hash, role) VALUES (?, ?, ?)", ("ayush.rawat@rbs.edu", mock_pass, "Student"))
            student_id = cursor.lastrowid
            cursor.execute("INSERT INTO Profiles (user_id, full_name, graduation_year, current_company, skill_tags) VALUES (?, ?, ?, ?, ?)",
                           (student_id, "Ayush Rawat", 2026, "RBS MTC Student", "Python, Flask, SQLite, Data Structures"))
            
            # Seed 4: Baseline Job Opening
            cursor.execute("INSERT INTO Job_Postings (posted_by, job_title, company_name, job_description, expiry_date) VALUES (?, ?, ?, ?, ?)",
                           (alumni_id, "Associate Software Engineer (SDE-1)", "Google", "Looking for Integrated MCA juniors with strong database fundamentals and backend structural routing skillsets.", "2026-07-31"))
            conn.commit()

# ==========================================
# UTILITY HELPER TO COMPOSE TEMPLATES
# ==========================================
def render_portal_page(page_body_content, **kwargs):
    """Safely injects child content into the master framework structure without template definition conflicts."""
    full_template = HTML_BASE.replace('<!-- INJECT_CONTENT_HERE -->', page_body_content)
    return render_template_string(full_template, **kwargs)

# ==========================================
# FLASK BACKEND ROUTING LOGIC
# ==========================================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('directory'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        full_name = request.form['full_name']
        grad_year = request.form.get('graduation_year', None)
        company = request.form.get('current_company', '')
        skills = request.form.get('skill_tags', '')
        
        hashed_pw = generate_password_hash(password)
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Users (email, password_hash, role) VALUES (?, ?, ?)", (email, hashed_pw, role))
                user_id = cursor.lastrowid
                cursor.execute("INSERT INTO Profiles (user_id, full_name, graduation_year, current_company, skill_tags) VALUES (?, ?, ?, ?, ?)",
                               (user_id, full_name, grad_year, company, skills))
                conn.commit()
            flash('Registration successful! Please authenticate below.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Identity conflict error: That email account is already indexed.', 'danger')
    return render_portal_page(HTML_REGISTER)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        with get_db() as conn:
            user = conn.execute("SELECT * FROM Users WHERE email = ?", (email,)).fetchone()
            
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['role'] = user['role']
            with get_db() as conn:
                prof = conn.execute("SELECT full_name FROM Profiles WHERE user_id = ?", (user['user_id'],)).fetchone()
                session['name'] = prof['full_name'] if prof else "System Member"
            flash(f"Welcome back, {session['name']}!", 'success')
            return redirect(url_for('directory'))
        else:
            flash('Invalid entry credentials. Please audit inputs.', 'danger')
    return render_portal_page(HTML_LOGIN)

@app.route('/directory')
def directory():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    search_company = request.args.get('company', '')
    search_skill = request.args.get('skill', '')
    
    query = "SELECT p.*, u.email, u.role FROM Profiles p JOIN Users u ON p.user_id = u.user_id WHERE u.role = 'Alumni'"
    params = []
    
    if search_company:
        query += " AND p.current_company LIKE ?"
        params.append(f"%{search_company}%")
    if search_skill:
        query += " AND p.skill_tags LIKE ?"
        params.append(f"%{search_skill}%")
        
    with get_db() as conn:
        alumni_records = conn.execute(query, params).fetchall()
    return render_portal_page(HTML_DIRECTORY, alumni=alumni_records, search_company=search_company, search_skill=search_skill)

@app.route('/jobs', methods=['GET', 'POST'])
def jobs():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST' and session.get('role') == 'Alumni':
        title = request.form['job_title']
        company = request.form['company_name']
        desc = request.form['job_description']
        expiry = request.form['expiry_date']
        
        with get_db() as conn:
            conn.execute("INSERT INTO Job_Postings (posted_by, job_title, company_name, job_description, expiry_date) VALUES (?, ?, ?, ?, ?)",
                         (session['user_id'], title, company, desc, expiry))
            conn.commit()
        flash('Career vacancy post published successfully!', 'success')
        return redirect(url_for('jobs'))
        
    with get_db() as conn:
        all_jobs = conn.execute("SELECT j.*, p.full_name as poster_name FROM Job_Postings j JOIN Profiles p ON j.posted_by = p.user_id ORDER BY j.job_id DESC").fetchall()
    return render_portal_page(HTML_JOBS, jobs=all_jobs)

@app.route('/logout')
def logout():
    session.clear()
    flash('Session securely closed.', 'info')
    return redirect(url_for('login'))

# ==========================================
# MASTER FRONTEND HTML STRING ARCHITECTURES
# ==========================================
HTML_BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alumni Connect Portal - RBS MTC, Agra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: 'Segoe UI', Arial, sans-serif; }
        .navbar-custom { background-color: #1a365d; }
        .card-custom { border-radius: 8px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark navbar-custom mb-4">
    <div class="container">
        <a class="navbar-brand fw-bold" href="#">RBS MTC Alumni Connect</a>
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav ms-auto">
                {% if session.get('user_id') %}
                    <li class="nav-item"><a class="nav-link text-white" href="{{ url_for('directory') }}">Alumni Directory</a></li>
                    <li class="nav-item"><a class="nav-link text-white" href="{{ url_for('jobs') }}">Job Board</a></li>
                    <li class="nav-item"><span class="nav-link text-warning fw-bold">📍 {{ session.get('name') }} ({{ session.get('role') }})</span></li>
                    <li class="nav-item"><a class="btn btn-danger btn-sm ms-2 mt-1" href="{{ url_for('logout') }}">Logout</a></li>
                {% else %}
                    <li class="nav-item"><a class="nav-link text-white" href="{{ url_for('login') }}">Login</a></li>
                    <li class="nav-item"><a class="nav-link text-white" href="{{ url_for('register') }}">Register</a></li>
                {% endif %}
            </ul>
        </div>
    </div>
</nav>
<div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                    {{ message }} <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <!-- INJECT_CONTENT_HERE -->
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

HTML_LOGIN = """
<div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card card-custom p-4 mt-4 bg-white">
            <h3 class="text-center fw-bold mb-1" style="color: #1a365d;">Account Authentication</h3>
            <p class="text-muted text-center small mb-4">Raja Balwant Singh Management Technical Campus, Agra</p>
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label fw-bold">Institutional Email</label>
                    <input type="email" name="email" class="form-control" required placeholder="name@example.com">
                </div>
                <div class="mb-4">
                    <label class="form-label fw-bold">Account Password</label>
                    <input type="password" name="password" class="form-control" required placeholder="••••••••">
                </div>
                <button type="submit" class="btn w-100 text-white fw-bold" style="background-color: #2b6cb0;">Verify & Enter Portal</button>
            </form>
            <div class="text-center mt-3">
                <a href="{{ url_for('register') }}" class="small text-decoration-none">New structural user? Register access profile here &rarr;</a>
            </div>
        </div>
    </div>
</div>
"""

HTML_REGISTER = """
<div class="row justify-content-center">
    <div class="col-md-7">
        <div class="card card-custom p-4 mb-5 bg-white">
            <h3 class="fw-bold mb-1" style="color: #1a365d;">Access Registration Form</h3>
            <p class="text-muted small mb-4">Complete your institutional record tracking information matrix.</p>
            <form method="POST">
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label class="form-label fw-bold">Full Profile Name</label>
                        <input type="text" name="full_name" class="form-control" required placeholder="Name">
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="form-label fw-bold">System Access Tier</label>
                        <select name="role" id="roleSelect" class="form-select" onchange="toggleAlumniFields()">
                            <option value="Student">Student (Current Batch)</option>
                            <option value="Alumni">Alumni (Graduated)</option>
                        </select>
                    </div>
                </div>
                <div class="mb-3">
                    <label class="form-label fw-bold">Secure Authentication Email</label>
                    <input type="email" name="email" class="form-control" required placeholder="email@rbsmtc.in">
                </div>
                <div class="mb-3">
                    <label class="form-label fw-bold">Account Password</label>
                    <input type="password" name="password" class="form-control" required placeholder="Generate a secure string">
                </div>
                <div id="alumniFields" style="display: none;" class="p-3 bg-light border rounded mb-3">
                    <h5 class="fw-bold text-secondary mb-3">Alumni Corporate Metrics</h5>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Graduation Year</label>
                            <input type="number" name="graduation_year" class="form-control" placeholder="2024">
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Current Corporate Employer</label>
                            <input type="text" name="current_company" class="form-control" placeholder="Google / Microsoft">
                        </div>
                    </div>
                    <div class="mb-2">
                        <label class="form-label">Technical Skill Tags (Comma Separated)</label>
                        <input type="text" name="skill_tags" class="form-control" placeholder="Java, Spring Boot, System Design">
                    </div>
                </div>
                <button type="submit" class="btn text-white w-100 fw-bold mt-2" style="background-color: #2b6cb0;">Commit Registration Registry</button>
            </form>
        </div>
    </div>
</div>
<script>
function toggleAlumniFields() {
    var role = document.getElementById("roleSelect").value;
    var fields = document.getElementById("alumniFields");
    fields.style.display = (role === "Alumni") ? "block" : "none";
}
</script>
"""

HTML_DIRECTORY = """
<div class="row">
    <div class="col-md-4">
        <div class="card card-custom p-4 bg-white mb-4">
            <h5 class="fw-bold border-bottom pb-2" style="color: #1a365d;">FILTER PANEL</h5>
            <form method="GET" action="{{ url_for('directory') }}">
                <div class="mb-3">
                    <label class="form-label small fw-bold text-muted">Target Company</label>
                    <input type="text" name="company" class="form-control" value="{{ search_company }}" placeholder="Search Company...">
                </div>
                <div class="mb-4">
                    <label class="form-label small fw-bold text-muted">Core Skillsets</label>
                    <input type="text" name="skill" class="form-control" value="{{ search_skill }}" placeholder="e.g. Java, React">
                </div>
                <button type="submit" class="btn btn-primary btn-sm w-100 fw-bold">Compute Filtering Matrix</button>
                <a href="{{ url_for('directory') }}" class="btn btn-outline-secondary btn-sm w-100 mt-2">Clear Filters</a>
            </form>
        </div>
    </div>
    <div class="col-md-8">
        <div class="card card-custom p-4 bg-white">
            <h5 class="fw-bold text-uppercase mb-4" style="color: #1a365d;">Active Alumni Records Directory</h5>
            {% if alumni %}
                {% for alum in alumni %}
                    <div class="card p-3 mb-3 border-start border-primary border-4 shadow-sm bg-white">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h5 class="fw-bold text-dark mb-1">{{ alum.full_name }}</h5>
                                <p class="mb-1 text-muted small">
                                    <strong>Batch:</strong> {{ alum.graduation_year }} | 
                                    <strong>Company:</strong> <span class="badge bg-success">{{ alum.current_company }}</span>
                                </p>
                                <p class="mb-0 text-secondary" style="font-size: 0.95rem;">
                                    <strong>Skills:</strong> <span class="text-primary font-monospace">{{ alum.skill_tags }}</span>
                                </p>
                            </div>
                            <span class="badge bg-light text-dark border">{{ alum.email }}</span>
                        </div>
                    </div>
                {% endfor %}
            {% else %}
                <div class="text-center py-5">
                    <p class="text-muted mb-0">No matching alumni profile indexes found for current query parameters.</p>
                </div>
            {% endif %}
        </div>
    </div>
</div>
"""

HTML_JOBS = """
<div class="row">
    {% if session.get('role') == 'Alumni' %}
    <div class="col-md-4">
        <div class="card card-custom p-4 bg-white mb-4">
            <h5 class="fw-bold border-bottom pb-2" style="color: #1a365d;">Publish Career Listing</h5>
            <form method="POST">
                <div class="mb-2">
                    <label class="form-label small mb-1">Designation Title</label>
                    <input type="text" name="job_title" class="form-control form-control-sm" required placeholder="e.g., SDE-1">
                </div>
                <div class="mb-2">
                    <label class="form-label small mb-1">Hiring Corporate Entity</label>
                    <input type="text" name="company_name" class="form-control form-control-sm" required placeholder="Corporate Brand">
                </div>
                <div class="mb-2">
                    <label class="form-label small mb-1">Active Cut-Off Deadline</label>
                    <input type="date" name="expiry_date" class="form-control form-control-sm" required>
                </div>
                <div class="mb-3">
                    <label class="form-label small mb-1">Listing Context Description</label>
                    <textarea name="job_description" rows="4" class="form-control form-control-sm" required placeholder="Enter role rules..."></textarea>
                </div>
                <button type="submit" class="btn btn-success btn-sm w-100 fw-bold">Publish to Job Board Feed</button>
            </form>
        </div>
    </div>
    {% endif %}
    <div class="col-md-{% if session.get('role') == 'Alumni' %}8{% else %}12{% endif %}">
        <div class="card card-custom p-4 bg-white">
            <h5 class="fw-bold mb-4" style="color: #1a365d;">INTERNAL JOB PLACEMENT STREAM</h5>
            {% if jobs %}
                {% for job in jobs %}
                    <div class="card p-3 mb-3 border-light bg-light">
                        <div class="d-flex justify-content-between">
                            <h5 class="fw-bold text-primary mb-1">{{ job.job_title }}</h5>
                            <span class="text-danger small fw-bold">Apply Before: {{ job.expiry_date }}</span>
                        </div>
                        <h6 class="text-secondary mb-2">Hiring Entity: <strong>{{ job.company_name }}</strong></h6>
                        <p class="small text-dark mb-3" style="line-height:1.5;">{{ job.job_description }}</p>
                        <div class="border-top pt-2 d-flex justify-content-between align-items-center">
                            <span class="text-muted small">Indexed by Alumni: <strong>{{ job.poster_name }}</strong></span>
                            <a href="mailto:verify@rbsmtc.in" class="btn btn-sm btn-outline-primary px-3 py-1">Submit Application</a>
                        </div>
                    </div>
                {% endfor %}
            {% else %}
                <div class="text-center py-5">
                    <p class="text-muted">No active professional opportunity streams listed currently.</p>
                </div>
            {% endif %}
        </div>
    </div>
</div>
"""

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
