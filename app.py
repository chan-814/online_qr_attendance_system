# ==============================================================
#  QR ATTENDANCE PRO  –  Flask Backend  (FINAL v4 – COMPLETE)
#  Features  : QR Gen + Location Lock + Face Verify + Admin QR Stats
#  Database  : qr_attendance_pro
#  Run       : python app.py
#  Visit     : http://localhost:5000
#  Admin     : admin@qrpro.com  /  admin123
# ==============================================================

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for)
import pymysql
import pymysql.cursors
import hashlib, uuid, qrcode, io, base64, json, random, string, math
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = 'qr_attendance_pro_secret_2024'

# ── Database ────────────────────────────────────────────────
DB_CONFIG = {
    'host'       : 'localhost',
    'user'       : 'root',
    'password'   : '',                    # WAMP default: empty password
    'database'   : 'qr_attendance_pro',   # SEPARATE from v1
    'charset'    : 'utf8',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

# ── Helpers ─────────────────────────────────────────────────
def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

def serialize(obj):
    if isinstance(obj, list):             return [serialize(i) for i in obj]
    if isinstance(obj, dict):             return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, (datetime, date)): return str(obj)
    return obj

def fmt_dt(dt):
    """Convert MySQL datetime string to ISO-8601 for JS new Date() in all browsers."""
    return str(dt).replace(' ', 'T')

def make_qr_image(data):
    """Generate QR PNG and return as base64 string."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f'[QR ERROR] {e}')
        return ''

def is_logged_in(role):
    return 'loggedin' in session and session.get('role') == role

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_notifications_to_class(class_id, title, message, db):
    """Create notification for every student in the given class."""
    with db.cursor() as cur:
        cur.execute('SELECT id FROM students WHERE class_id=%s', (class_id,))
        for s in cur.fetchall():
            cur.execute(
                'INSERT INTO notifications (student_id,title,message) VALUES (%s,%s,%s)',
                (s['id'], title, message)
            )

def haversine_distance(lat1, lon1, lat2, lon2):
    """Return distance in METRES between two GPS coordinates using Haversine formula."""
    R = 6_371_000  # Earth radius in metres
    phi1    = math.radians(float(lat1))
    phi2    = math.radians(float(lat2))
    d_phi   = math.radians(float(lat2) - float(lat1))
    d_lam   = math.radians(float(lon2) - float(lon1))
    a = (math.sin(d_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


# ============================================================
# INDEX
# ============================================================
@app.route('/')
def index():
    return render_template('index.html')


# ============================================================
# STUDENT AUTH
# ============================================================
@app.route('/student/login', methods=['GET','POST'])
def student_login():
    msg = ''
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        pw    = request.form.get('password','')
        db    = get_db()
        try:
            with db.cursor() as cur:
                cur.execute('SELECT * FROM students WHERE email=%s AND password=%s',
                            (email, hash_pw(pw)))
                s = cur.fetchone()
        finally:
            db.close()
        if s:
            session.update(loggedin=True, id=s['id'], name=s['name'], role='student')
            return redirect(url_for('student_dashboard'))
        msg = 'Invalid email or password.'
    return render_template('student/login.html', msg=msg)


@app.route('/student/register', methods=['GET','POST'])
def student_register():
    msg = ''; classes = []
    db  = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT * FROM classes')
            classes = cur.fetchall()
        if request.method == 'POST':
            name  = request.form.get('name','').strip()
            reg   = request.form.get('register_number','').strip()
            email = request.form.get('email','').strip()
            pw    = request.form.get('password','')
            cid   = request.form.get('class_id') or None
            dept  = request.form.get('department','').strip()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        'INSERT INTO students (name,register_number,email,password,'
                        'class_id,department) VALUES (%s,%s,%s,%s,%s,%s)',
                        (name, reg, email, hash_pw(pw), cid, dept))
                db.commit()
                return redirect(url_for('student_login'))
            except Exception as e:
                msg = 'Registration failed: ' + str(e)
    finally:
        db.close()
    return render_template('student/register.html', msg=msg, classes=classes)


@app.route('/student/dashboard')
def student_dashboard():
    if not is_logged_in('student'):
        return redirect(url_for('student_login'))
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'SELECT s.*,c.class_name FROM students s '
                'LEFT JOIN classes c ON s.class_id=c.id WHERE s.id=%s',
                (session['id'],))
            student = cur.fetchone()
            cur.execute('SELECT COUNT(*) AS cnt FROM notifications '
                        'WHERE student_id=%s AND is_read=0', (session['id'],))
            unread = cur.fetchone()['cnt']
            cur.execute('SELECT id FROM face_data WHERE student_id=%s', (session['id'],))
            face_registered = cur.fetchone() is not None
    finally:
        db.close()
    return render_template('student/dashboard.html',
                           student=student, unread=unread,
                           face_registered=face_registered)


# ============================================================
# TEACHER AUTH
# ============================================================
@app.route('/teacher/login', methods=['GET','POST'])
def teacher_login():
    msg = ''
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        pw    = request.form.get('password','')
        db    = get_db()
        try:
            with db.cursor() as cur:
                cur.execute('SELECT * FROM teachers WHERE email=%s AND password=%s',
                            (email, hash_pw(pw)))
                t = cur.fetchone()
        finally:
            db.close()
        if t:
            session.update(loggedin=True, id=t['id'], name=t['name'], role='teacher')
            return redirect(url_for('teacher_dashboard'))
        msg = 'Invalid email or password.'
    return render_template('teacher/login.html', msg=msg)


@app.route('/teacher/register', methods=['GET','POST'])
def teacher_register():
    msg = ''; classes = []
    db  = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT * FROM classes')
            classes = cur.fetchall()
        if request.method == 'POST':
            name  = request.form.get('name','').strip()
            tid   = request.form.get('teacher_id','').strip()
            email = request.form.get('email','').strip()
            pw    = request.form.get('password','')
            dept  = request.form.get('department','').strip()
            cid   = request.form.get('class_id') or None
            try:
                with db.cursor() as cur:
                    cur.execute(
                        'INSERT INTO teachers (name,teacher_id,email,password,'
                        'department,class_id) VALUES (%s,%s,%s,%s,%s,%s)',
                        (name, tid, email, hash_pw(pw), dept, cid))
                db.commit()
                return redirect(url_for('teacher_login'))
            except Exception as e:
                msg = 'Registration failed: ' + str(e)
    finally:
        db.close()
    return render_template('teacher/register.html', msg=msg, classes=classes)


@app.route('/teacher/dashboard')
def teacher_dashboard():
    if not is_logged_in('teacher'):
        return redirect(url_for('teacher_login'))
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'SELECT t.*,c.class_name FROM teachers t '
                'LEFT JOIN classes c ON t.class_id=c.id WHERE t.id=%s',
                (session['id'],))
            teacher = cur.fetchone()
            cur.execute('SELECT * FROM classes')
            classes = cur.fetchall()
    finally:
        db.close()
    return render_template('teacher/dashboard.html', teacher=teacher, classes=classes)


# ============================================================
# ADMIN AUTH
# ============================================================
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    msg = ''
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        pw    = request.form.get('password','')
        db    = get_db()
        try:
            with db.cursor() as cur:
                cur.execute('SELECT * FROM admins WHERE email=%s AND password=%s',
                            (email, hash_pw(pw)))
                a = cur.fetchone()
        finally:
            db.close()
        if a:
            session.update(loggedin=True, id=a['id'], name=a['name'], role='admin')
            return redirect(url_for('admin_dashboard'))
        msg = 'Invalid email or password.'
    return render_template('admin/login.html', msg=msg)


@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_logged_in('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin/dashboard.html')


# ============================================================
# LOGOUT
# ============================================================
@app.route('/logout')
def logout():
    role = session.get('role','')
    session.clear()
    if role == 'student': return redirect(url_for('student_login'))
    if role == 'teacher': return redirect(url_for('teacher_login'))
    return redirect(url_for('admin_login'))


# ============================================================
# FORGOT / RESET PASSWORD
# ============================================================
@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    msg=''; msg_type=''; otp_show=''
    if request.method == 'POST':
        email     = request.form.get('email','').strip()
        user_type = request.form.get('user_type','student')
        db        = get_db()
        try:
            table = {'student':'students','teacher':'teachers','admin':'admins'}[user_type]
            with db.cursor() as cur:
                cur.execute(f'SELECT id FROM {table} WHERE email=%s', (email,))
                user = cur.fetchone()
            if not user:
                msg='No account found with that email address.'; msg_type='error'
            else:
                otp        = generate_otp()
                expires_at = datetime.now() + timedelta(minutes=10)
                with db.cursor() as cur:
                    cur.execute('DELETE FROM password_resets WHERE email=%s AND user_type=%s',
                                (email, user_type))
                    cur.execute('INSERT INTO password_resets '
                                '(email,otp,user_type,expires_at) VALUES (%s,%s,%s,%s)',
                                (email, otp, user_type, expires_at))
                db.commit()
                otp_show=otp
                msg='Your OTP is shown below. It is valid for 10 minutes.'
                msg_type='success'
        finally:
            db.close()
    return render_template('auth/forgot_password.html',
                           msg=msg, msg_type=msg_type, otp_show=otp_show)


@app.route('/reset-password', methods=['GET','POST'])
def reset_password():
    msg=''; msg_type=''
    if request.method == 'POST':
        email     = request.form.get('email','').strip()
        otp       = request.form.get('otp','').strip()
        new_pw    = request.form.get('new_password','')
        user_type = request.form.get('user_type','student')
        db        = get_db()
        try:
            with db.cursor() as cur:
                cur.execute('SELECT * FROM password_resets WHERE email=%s AND otp=%s '
                            'AND user_type=%s AND is_used=0', (email, otp, user_type))
                reset = cur.fetchone()
            if not reset:
                msg='Invalid OTP. Please try again.'; msg_type='error'
            elif datetime.now() > reset['expires_at']:
                msg='OTP has expired. Please request a new one.'; msg_type='error'
            else:
                table = {'student':'students','teacher':'teachers','admin':'admins'}[user_type]
                with db.cursor() as cur:
                    cur.execute(f'UPDATE {table} SET password=%s WHERE email=%s',
                                (hash_pw(new_pw), email))
                    cur.execute('UPDATE password_resets SET is_used=1 WHERE id=%s',
                                (reset['id'],))
                db.commit()
                msg='Password reset successfully! You can now login.'; msg_type='success'
        finally:
            db.close()
    return render_template('auth/reset_password.html', msg=msg, msg_type=msg_type)


# ============================================================
# API – QR CODE GENERATION  (with optional Location Lock)
# ============================================================
@app.route('/api/generate_qr', methods=['POST'])
def generate_qr():
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401

    data     = request.get_json()
    cid      = data.get('class_id')
    subject  = data.get('subject','').strip()
    expiry   = int(data.get('expiry_minutes', 2))

    # Location fields (optional — only set when teacher enables location lock)
    location_enabled = data.get('location_enabled', False)
    teacher_lat      = data.get('teacher_lat')   if location_enabled else None
    teacher_lng      = data.get('teacher_lng')   if location_enabled else None
    location_radius  = int(data.get('location_radius', 100))

    if not cid or not subject:
        return jsonify({'error':'Class and subject are required.'}), 400

    # Validate: if location lock enabled, coordinates must be present
    if location_enabled and (teacher_lat is None or teacher_lng is None):
        return jsonify({'error':'Location lock enabled but teacher GPS coordinates not received. '
                                'Please allow location access in your browser and try again.'}), 400

    sid        = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(minutes=expiry)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'INSERT INTO qr_sessions '
                '(session_id,teacher_id,class_id,subject,expires_at,'
                ' teacher_lat,teacher_lng,location_radius) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                (sid, session['id'], cid, subject, expires_at,
                 teacher_lat, teacher_lng, location_radius))
        # Notify class students
        loc_msg = (f'Location verification is enabled for this session '
                   f'(must be within {location_radius}m of classroom).')  \
                  if location_enabled else ''
        send_notifications_to_class(
            cid,
            f'New QR Session: {subject}',
            f'Your teacher started attendance for "{subject}". '
            f'Open QR Scanner now! Valid for {expiry} minute(s). {loc_msg}'.strip(),
            db)
        db.commit()
    except Exception as e:
        try: db.rollback()
        except: pass
        db.close()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        db.close()

    qr_image = make_qr_image(json.dumps({'session_id': sid, 'subject': subject}))
    if not qr_image:
        return jsonify({'error':'QR image generation failed.'}), 500

    return jsonify({
        'success'         : True,
        'session_id'      : sid,
        'qr_image'        : qr_image,
        'expires_at'      : fmt_dt(expires_at),   # T-separator for JS Date()
        'expiry_minutes'  : expiry,
        'location_enabled': location_enabled,
        'location_radius' : location_radius
    })


# ============================================================
# API – MARK ATTENDANCE  (with Location Distance Check)
# ============================================================
@app.route('/api/scan_attendance', methods=['POST'])
def scan_attendance():
    if not is_logged_in('student'):
        return jsonify({'error':'Unauthorized'}), 401

    data = request.get_json()
    try:
        qd         = json.loads(data.get('qr_data','{}'))
        session_id = qd['session_id']
        subject    = qd['subject']
    except Exception:
        return jsonify({'error':'Invalid QR code data.'}), 400

    # Student GPS (may be None if student denied location)
    student_lat = data.get('student_lat')
    student_lng = data.get('student_lng')

    db = get_db()
    try:
        with db.cursor() as cur:
            # 1. Check session exists and is active
            cur.execute('SELECT * FROM qr_sessions WHERE session_id=%s AND is_active=1',
                        (session_id,))
            qs = cur.fetchone()
            if not qs:
                return jsonify({'error':'QR code is invalid or has already been deactivated.'}), 400

            # 2. Check expiry
            if datetime.now() > qs['expires_at']:
                cur.execute('UPDATE qr_sessions SET is_active=0 WHERE session_id=%s',
                            (session_id,))
                db.commit()
                return jsonify({'error':'QR code has expired. Ask your teacher to generate a new one.'}), 400

            # 3. Check duplicate attendance
            cur.execute('SELECT id FROM attendance WHERE student_id=%s AND session_id=%s',
                        (session['id'], session_id))
            if cur.fetchone():
                return jsonify({'error':'Attendance already marked for this session.'}), 400

            # 4. Check class match
            cur.execute('SELECT class_id FROM students WHERE id=%s', (session['id'],))
            st = cur.fetchone()
            if not st or str(st['class_id']) != str(qs['class_id']):
                return jsonify({'error':'This QR code is not for your class.'}), 400

            # 5. ── LOCATION VERIFICATION ──────────────────────────────
            #    Only enforced when teacher set their coordinates at QR generation time
            if qs['teacher_lat'] is not None and qs['teacher_lng'] is not None:
                radius = int(qs['location_radius'] or 100)

                if student_lat is None or student_lng is None:
                    return jsonify({
                        'error': (f'This QR session requires location verification. '
                                  f'Please enable location (GPS) on your device and '
                                  f'try again.')
                    }), 400

                try:
                    distance = haversine_distance(
                        qs['teacher_lat'], qs['teacher_lng'],
                        student_lat, student_lng
                    )
                    distance_m = round(distance)
                except Exception as ex:
                    return jsonify({'error': f'Location calculation error: {str(ex)}'}), 400

                if distance > radius:
                    return jsonify({
                        'error': (f'Location mismatch! You are {distance_m}m away from the '
                                  f'classroom. The allowed radius is {radius}m. '
                                  f'Please move closer and try again.')
                    }), 400
                # Location OK — proceed

            # 6. Mark attendance (with student GPS if available)
            cur.execute(
                "INSERT INTO attendance "
                "(student_id,session_id,class_id,subject,status,scan_lat,scan_lng) "
                "VALUES (%s,%s,%s,%s,'Present',%s,%s)",
                (session['id'], session_id, qs['class_id'], subject,
                 student_lat if student_lat is not None else None,
                 student_lng if student_lng is not None else None))
        db.commit()
    finally:
        db.close()

    return jsonify({'success': True,
                    'message': f'Attendance marked successfully for {subject}!'})


# ============================================================
# API – FACE VERIFICATION
# ============================================================
@app.route('/api/face/register', methods=['POST'])
def face_register():
    if not is_logged_in('student'):
        return jsonify({'error':'Unauthorized'}), 401
    desc = request.get_json().get('descriptor')
    if not desc:
        return jsonify({'error':'No face data received.'}), 400
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT id FROM face_data WHERE student_id=%s', (session['id'],))
            if cur.fetchone():
                cur.execute('UPDATE face_data SET face_descriptor=%s WHERE student_id=%s',
                            (json.dumps(desc), session['id']))
            else:
                cur.execute('INSERT INTO face_data (student_id,face_descriptor) VALUES (%s,%s)',
                            (session['id'], json.dumps(desc)))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True, 'message':'Face registered successfully!'})


@app.route('/api/face/get')
def face_get():
    if not is_logged_in('student'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT face_descriptor FROM face_data WHERE student_id=%s',
                        (session['id'],))
            row = cur.fetchone()
    finally:
        db.close()
    if not row:
        return jsonify({'registered':False})
    return jsonify({'registered':True, 'descriptor':json.loads(row['face_descriptor'])})


# ============================================================
# API – NOTIFICATIONS
# ============================================================
@app.route('/api/notifications')
def get_notifications():
    if not is_logged_in('student'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT * FROM notifications WHERE student_id=%s '
                        'ORDER BY created_at DESC LIMIT 20', (session['id'],))
            notifs = cur.fetchall()
            cur.execute('SELECT COUNT(*) AS cnt FROM notifications '
                        'WHERE student_id=%s AND is_read=0', (session['id'],))
            unread = cur.fetchone()['cnt']
    finally:
        db.close()
    return jsonify({'notifications':serialize(notifs), 'unread':unread})


@app.route('/api/notifications/mark_read', methods=['POST'])
def mark_notifications_read():
    if not is_logged_in('student'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('UPDATE notifications SET is_read=1 WHERE student_id=%s',
                        (session['id'],))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


# ============================================================
# API – TIMETABLE
# ============================================================
@app.route('/api/timetable/<int:class_id>')
def get_timetable(class_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT tt.*, t.name AS teacher_name
                   FROM timetable tt
                   LEFT JOIN teachers t ON tt.teacher_id=t.id
                   WHERE tt.class_id=%s
                   ORDER BY FIELD(tt.day_name,
                     'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'),
                   tt.period_no""",
                (class_id,))
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'timetable':serialize(rows)})


@app.route('/api/timetable/add', methods=['POST'])
def add_timetable():
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'INSERT INTO timetable (class_id,day_name,period_no,subject,'
                'teacher_id,start_time,end_time) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (d['class_id'],d['day_name'],d['period_no'],d['subject'],
                 d.get('teacher_id') or session['id'],d['start_time'],d['end_time']))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'error':str(e)}), 400
    finally:
        db.close()


@app.route('/api/timetable/delete/<int:tid>', methods=['DELETE'])
def delete_timetable(tid):
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('DELETE FROM timetable WHERE id=%s', (tid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


# ============================================================
# API – STUDENT DATA
# ============================================================
@app.route('/api/student/attendance')
def api_student_attendance():
    if not is_logged_in('student'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT a.id, a.subject, a.status,
                          DATE_FORMAT(a.scanned_at,'%%Y-%%m-%%d') AS date,
                          DATE_FORMAT(a.scanned_at,'%%H:%%i')     AS time,
                          c.class_name
                   FROM attendance a
                   LEFT JOIN classes c ON a.class_id=c.id
                   WHERE a.student_id=%s
                   ORDER BY a.scanned_at DESC""",
                (session['id'],))
            records = cur.fetchall()
            cur.execute('SELECT class_id FROM students WHERE id=%s', (session['id'],))
            st = cur.fetchone(); total = 0
            if st and st['class_id']:
                cur.execute('SELECT COUNT(*) AS cnt FROM qr_sessions WHERE class_id=%s',
                            (st['class_id'],))
                total = cur.fetchone()['cnt']
    finally:
        db.close()
    present = len(records)
    pct     = round(present / total * 100, 1) if total > 0 else 0
    return jsonify({'attendance':records,'present':present,'total':total,'percentage':pct})


# ============================================================
# API – TEACHER DATA
# ============================================================
@app.route('/api/teacher/students')
def api_teacher_students():
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'SELECT s.*,c.class_name FROM students s '
                'LEFT JOIN classes c ON s.class_id=c.id '
                'WHERE s.class_id=(SELECT class_id FROM teachers WHERE id=%s)',
                (session['id'],))
            students = cur.fetchall()
    finally:
        db.close()
    return jsonify({'students':serialize(students)})


@app.route('/api/teacher/all_students/<int:class_id>')
def api_class_students(class_id):
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'SELECT s.*,c.class_name FROM students s '
                'LEFT JOIN classes c ON s.class_id=c.id WHERE s.class_id=%s',
                (class_id,))
            students = cur.fetchall()
    finally:
        db.close()
    return jsonify({'students':serialize(students)})


@app.route('/api/teacher/student/<int:sid>', methods=['PUT'])
def update_student(sid):
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('UPDATE students SET name=%s,register_number=%s,'
                        'email=%s,department=%s WHERE id=%s',
                        (d['name'],d['register_number'],d['email'],d['department'],sid))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/teacher/student/<int:sid>', methods=['DELETE'])
def delete_student(sid):
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('DELETE FROM students WHERE id=%s', (sid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/teacher/attendance_report')
def teacher_report():
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    dt  = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    cid = request.args.get('class_id')
    db  = get_db()
    try:
        with db.cursor() as cur:
            q = """SELECT a.id, a.subject, a.status, a.scan_lat, a.scan_lng,
                          s.name AS student_name, s.register_number, c.class_name,
                          DATE_FORMAT(a.scanned_at,'%%Y-%%m-%%d %%H:%%i') AS scanned_at
                   FROM attendance a
                   JOIN students s ON a.student_id=s.id
                   LEFT JOIN classes c ON a.class_id=c.id
                   WHERE DATE(a.scanned_at)=%s"""
            params = [dt]
            if cid:
                q += ' AND a.class_id=%s'; params.append(cid)
            q += ' ORDER BY a.scanned_at DESC'
            cur.execute(q, params)
            report = cur.fetchall()
    finally:
        db.close()
    return jsonify({'report':report})


@app.route('/api/qr_status/<sess_id>')
def qr_status(sess_id):
    if not is_logged_in('teacher'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT * FROM qr_sessions WHERE session_id=%s', (sess_id,))
            qs = cur.fetchone()
            if not qs: return jsonify({'error':'Not found'}), 404
            cur.execute('SELECT COUNT(*) AS cnt FROM attendance WHERE session_id=%s',
                        (sess_id,))
            cnt = cur.fetchone()['cnt']
    finally:
        db.close()
    return jsonify({
        'expired'   : datetime.now() > qs['expires_at'],
        'scan_count': cnt,
        'expires_at': fmt_dt(qs['expires_at'])
    })


# ============================================================
# API – ADMIN STATS
# ============================================================
@app.route('/api/admin/stats')
def admin_stats():
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS c FROM students');    s  = cur.fetchone()['c']
            cur.execute('SELECT COUNT(*) AS c FROM teachers');    t  = cur.fetchone()['c']
            cur.execute('SELECT COUNT(*) AS c FROM classes');     cl = cur.fetchone()['c']
            cur.execute('SELECT COUNT(*) AS c FROM attendance');  a  = cur.fetchone()['c']
            cur.execute('SELECT COUNT(*) AS c FROM qr_sessions'); qs = cur.fetchone()['c']
    finally:
        db.close()
    return jsonify({'students':s,'teachers':t,'classes':cl,'attendance':a,'sessions':qs})


@app.route('/api/admin/qr_stats')
def admin_qr_stats():
    """Per-class QR generation count with reset support."""
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.class_name,
                    c.department,
                    c.qr_count_offset,
                    COALESCE(t.name,'Unassigned')         AS teacher_name,
                    COUNT(q.id)                           AS total_sessions,
                    (COUNT(q.id) - c.qr_count_offset)     AS current_count,
                    MAX(q.created_at)                     AS last_generated,
                    SUM(CASE WHEN q.teacher_lat IS NOT NULL THEN 1 ELSE 0 END)
                                                          AS loc_locked_sessions
                FROM classes c
                LEFT JOIN teachers t    ON c.teacher_id=t.id
                LEFT JOIN qr_sessions q ON q.class_id=c.id
                GROUP BY c.id, c.class_name, c.department,
                         c.qr_count_offset, t.name
                ORDER BY current_count DESC
            """)
            stats = cur.fetchall()
    finally:
        db.close()
    return jsonify({'stats':serialize(stats)})


@app.route('/api/admin/qr_reset/<int:class_id>', methods=['POST'])
def admin_qr_reset(class_id):
    """Reset displayed QR count to 0 by updating offset to current total."""
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS cnt FROM qr_sessions WHERE class_id=%s',
                        (class_id,))
            total = cur.fetchone()['cnt']
            cur.execute('UPDATE classes SET qr_count_offset=%s WHERE id=%s',
                        (total, class_id))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True, 'message':'QR count reset to 0 successfully.'})


@app.route('/api/admin/qr_sessions')
def admin_qr_sessions():
    """List all QR sessions with scan counts for admin view."""
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    class_id = request.args.get('class_id')
    db = get_db()
    try:
        with db.cursor() as cur:
            q = """SELECT qs.id, qs.session_id, qs.subject, qs.is_active,
                          qs.teacher_lat, qs.teacher_lng, qs.location_radius,
                          c.class_name, t.name AS teacher_name,
                          DATE_FORMAT(qs.created_at,'%%Y-%%m-%%d %%H:%%i') AS created_at,
                          DATE_FORMAT(qs.expires_at,'%%Y-%%m-%%d %%H:%%i') AS expires_at,
                          (qs.expires_at < NOW()) AS is_expired,
                          COUNT(a.id) AS scan_count
                   FROM qr_sessions qs
                   LEFT JOIN classes  c ON qs.class_id  = c.id
                   LEFT JOIN teachers t ON qs.teacher_id = t.id
                   LEFT JOIN attendance a ON a.session_id = qs.session_id
                   {where}
                   GROUP BY qs.id
                   ORDER BY qs.created_at DESC
                   LIMIT 200"""
            if class_id:
                cur.execute(q.format(where='WHERE qs.class_id=%s'), (class_id,))
            else:
                cur.execute(q.format(where=''), ())
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'sessions': serialize(rows)})


@app.route('/api/admin/session_deactivate/<int:sid>', methods=['POST'])
def admin_session_deactivate(sid):
    """Deactivate a specific QR session."""
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('UPDATE qr_sessions SET is_active=0 WHERE id=%s', (sid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success': True})


@app.route('/api/admin/session_delete/<int:sid>', methods=['DELETE'])
def admin_session_delete(sid):
    """Permanently delete a QR session and its attendance records."""
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            # Get session_id string first (needed to delete attendance)
            cur.execute('SELECT session_id FROM qr_sessions WHERE id=%s', (sid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Session not found.'}), 404
            cur.execute('DELETE FROM attendance WHERE session_id=%s', (row['session_id'],))
            cur.execute('DELETE FROM qr_sessions WHERE id=%s', (sid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success': True})


@app.route('/api/admin/sessions_reset_class/<int:class_id>', methods=['POST'])
def admin_sessions_reset_class(class_id):
    """Deactivate ALL QR sessions for a class."""
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('UPDATE qr_sessions SET is_active=0 WHERE class_id=%s AND is_active=1',
                        (class_id,))
            affected = cur.rowcount
        db.commit()
    finally:
        db.close()
    return jsonify({'success': True, 'deactivated': affected})


@app.route('/api/admin/attendance_report')
def admin_attendance_report():
    """Full attendance report for admin — filterable by date, class, student."""
    if not is_logged_in('admin'):
        return jsonify({'error':'Unauthorized'}), 401
    date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
    date_to   = request.args.get('date_to',   datetime.now().strftime('%Y-%m-%d'))
    class_id  = request.args.get('class_id')
    search    = request.args.get('search', '').strip()
    db = get_db()
    try:
        with db.cursor() as cur:
            q = """SELECT a.id, a.subject, a.status, a.scan_lat, a.scan_lng,
                          s.name AS student_name, s.register_number,
                          c.class_name, c.department,
                          DATE_FORMAT(a.scanned_at,'%%Y-%%m-%%d') AS date,
                          DATE_FORMAT(a.scanned_at,'%%H:%%i')     AS time,
                          DATE_FORMAT(a.scanned_at,'%%Y-%%m-%%d %%H:%%i') AS scanned_at
                   FROM attendance a
                   JOIN students s ON a.student_id = s.id
                   LEFT JOIN classes c ON a.class_id = c.id
                   WHERE DATE(a.scanned_at) BETWEEN %s AND %s"""
            params = [date_from, date_to]
            if class_id:
                q += ' AND a.class_id=%s'; params.append(class_id)
            if search:
                q += ' AND (s.name LIKE %s OR s.register_number LIKE %s)'
                params.extend([f'%{search}%', f'%{search}%'])
            q += ' ORDER BY a.scanned_at DESC LIMIT 500'
            cur.execute(q, params)
            report = cur.fetchall()
    finally:
        db.close()
    return jsonify({'report': serialize(report), 'count': len(report)})


# ============================================================
# API – ADMIN CRUD
# ============================================================
@app.route('/api/admin/students')
def admin_students():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT s.*,c.class_name FROM students s '
                        'LEFT JOIN classes c ON s.class_id=c.id')
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'students':serialize(rows)})


@app.route('/api/admin/student', methods=['POST'])
def admin_add_student():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'INSERT INTO students (name,register_number,email,password,'
                'class_id,department) VALUES (%s,%s,%s,%s,%s,%s)',
                (d['name'],d['register_number'],d['email'],hash_pw(d['password']),
                 d.get('class_id') or None, d.get('department')))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'error':str(e)}), 400
    finally:
        db.close()


@app.route('/api/admin/student/<int:sid>', methods=['PUT'])
def admin_update_student(sid):
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('UPDATE students SET name=%s,register_number=%s,email=%s,'
                        'class_id=%s,department=%s WHERE id=%s',
                        (d['name'],d['register_number'],d['email'],
                         d.get('class_id') or None, d.get('department'),sid))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/admin/student/<int:sid>', methods=['DELETE'])
def admin_delete_student(sid):
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('DELETE FROM students WHERE id=%s', (sid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/admin/teachers')
def admin_teachers():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT t.*,c.class_name FROM teachers t '
                        'LEFT JOIN classes c ON t.class_id=c.id')
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'teachers':serialize(rows)})


@app.route('/api/admin/teacher', methods=['POST'])
def admin_add_teacher():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'INSERT INTO teachers (name,teacher_id,email,password,'
                'department,class_id) VALUES (%s,%s,%s,%s,%s,%s)',
                (d['name'],d['teacher_id'],d['email'],hash_pw(d['password']),
                 d.get('department'), d.get('class_id') or None))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'error':str(e)}), 400
    finally:
        db.close()


@app.route('/api/admin/teacher/<int:tid>', methods=['PUT'])
def admin_update_teacher(tid):
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('UPDATE teachers SET name=%s,teacher_id=%s,email=%s,'
                        'department=%s,class_id=%s WHERE id=%s',
                        (d['name'],d['teacher_id'],d['email'],
                         d.get('department'), d.get('class_id') or None, tid))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/admin/teacher/<int:tid>', methods=['DELETE'])
def admin_delete_teacher(tid):
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('DELETE FROM teachers WHERE id=%s', (tid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/admin/classes')
def admin_classes():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT c.*,t.name AS teacher_name FROM classes c '
                        'LEFT JOIN teachers t ON c.teacher_id=t.id')
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'classes':serialize(rows)})


@app.route('/api/admin/class', methods=['POST'])
def admin_add_class():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('INSERT INTO classes (class_name,department,teacher_id) '
                        'VALUES (%s,%s,%s)',
                        (d['class_name'],d['department'],d.get('teacher_id') or None))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'error':str(e)}), 400
    finally:
        db.close()


@app.route('/api/admin/class/<int:cid>', methods=['PUT'])
def admin_update_class(cid):
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    d = request.get_json(); db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('UPDATE classes SET class_name=%s,department=%s,'
                        'teacher_id=%s WHERE id=%s',
                        (d['class_name'],d['department'],
                         d.get('teacher_id') or None, cid))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/admin/class/<int:cid>', methods=['DELETE'])
def admin_delete_class(cid):
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('DELETE FROM classes WHERE id=%s', (cid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success':True})


@app.route('/api/classes')
def get_all_classes():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT * FROM classes')
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'classes':rows})


@app.route('/api/teachers_list')
def get_teachers_list():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT id,name,teacher_id FROM teachers')
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'teachers':rows})


# ============================================================
# API – ADMIN SELF-MANAGEMENT  (add / list / delete admins)
# ============================================================
@app.route('/api/admin/admins')
def admin_list_admins():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, "
                "DATE_FORMAT(created_at,'%%Y-%%m-%%d') AS created_at "
                "FROM admins ORDER BY id", ())
            rows = cur.fetchall()
    finally:
        db.close()
    return jsonify({'admins': rows})


@app.route('/api/admin/admin', methods=['POST'])
def admin_add_admin():
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    d  = request.get_json()
    name  = (d.get('name') or '').strip()
    email = (d.get('email') or '').strip()
    pw    = (d.get('password') or '')
    if not name or not email or not pw:
        return jsonify({'error': 'Name, email and password are required.'}), 400
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('INSERT INTO admins (name,email,password) VALUES (%s,%s,%s)',
                        (name, email, hash_pw(pw)))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/admin/admin/<int:aid>', methods=['DELETE'])
def admin_delete_admin(aid):
    if not is_logged_in('admin'): return jsonify({'error':'Unauthorized'}), 401
    # Prevent self-deletion
    if aid == session['id']:
        return jsonify({'error': 'You cannot delete your own account.'}), 400
    db = get_db()
    try:
        with db.cursor() as cur:
            # Make sure at least one admin remains
            cur.execute('SELECT COUNT(*) AS cnt FROM admins')
            if cur.fetchone()['cnt'] <= 1:
                return jsonify({'error': 'Cannot delete the last admin account.'}), 400
            cur.execute('DELETE FROM admins WHERE id=%s', (aid,))
        db.commit()
    finally:
        db.close()
    return jsonify({'success': True})


# ============================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
