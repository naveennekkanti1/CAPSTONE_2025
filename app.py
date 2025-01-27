from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from werkzeug.utils import secure_filename
import os


app = Flask(__name__)
app.config['MONGO_URI'] = "mongodb://localhost:27017/RAPACT"
app.secret_key = 'your_secret_key'  # Used for session management

# File upload settings
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png'}

mongo = PyMongo(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# File type check function
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Home route
@app.route('/')
def home():
    user_logged_in = 'user_id' in session
    return render_template('home.html', user_logged_in=user_logged_in)

@app.route('/about')
def about():
    return render_template('about.html')

# Register Patient Route
@app.route('/register_patient', methods=['GET', 'POST'])
def register_patient():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        photo = request.files['photo']

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register_patient'))

        if photo and allowed_file(photo.filename):
            photo_filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        else:
            flash("Invalid file type. Only PDF, JPG, JPEG, or PNG files are allowed.", "danger")
            return redirect(url_for('register_patient'))

        if mongo.db.users.find_one({'email': email}):
            flash("Email already registered. Please use a different email.", "danger")
            return redirect(url_for('register_patient'))

        hashed_password = generate_password_hash(password)

        mongo.db.users.insert_one({
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': hashed_password,
            'role': 'patient',
            'photo': photo_filename
        })

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('patient_register.html')

# Register Doctor Route
@app.route('/register_doctor', methods=['GET', 'POST'])
def register_doctor():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']  # 'patient' or 'doctor'
        photo = request.files['photo']

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register'))

        # Check if a photo was uploaded and is valid
        photo_filename = None
        if photo and allowed_file(photo.filename):
            photo_filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        else:
            flash("Invalid file type. Only PDF, JPG, JPEG, or PNG files are allowed.", "danger")
            return redirect(url_for('register'))

        if mongo.db.users.find_one({'email': email}):
            flash("Email already registered. Please use a different email.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        # Common user fields
        user_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': hashed_password,
            'role': role,
            'photo': photo_filename,
        }

        # Additional fields for doctors
        if role == 'doctor':
            user_data.update({
                'age': request.form['age'],
                'gender': request.form['gender'],
                'phone': request.form['phone'],
                'experience_years': request.form['experience_years'],
                'specialization': request.form['specialization'],
                'brief_experience': request.form['brief_experience'],
                'address': {
                    'house_no': request.form['house_no'],
                    'city': request.form['city'],
                    'state': request.form['state'],
                    'country': request.form['country'],
                    'pincode': request.form['pincode'],
                },
                'is_verified': False,  # Set to False until verified by admin
            })

        mongo.db.users.insert_one(user_data)

        if role == 'doctor':
            flash("Registration successful! Your details will be verified by the admin.", "success")
        else:
            flash("Registration successful! Please log in.", "success")

        return redirect(url_for('login'))

    return render_template('doctor_register.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        user = mongo.db.users.find_one({'email': email, 'role': role})

        if user and check_password_hash(user['password'], password):
            if role == 'doctor' and not user.get('verified', False):
                flash("Your account is pending admin verification.", "danger")
                return redirect(url_for('login'))

            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        elif role == 'patient':
            return redirect(url_for('patient_dashboard'))
    flash("Please log in first.", "danger")
    return redirect(url_for('login'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' in session and session.get('role') == 'admin':
        # Admin stats
        patients_count = mongo.db.users.count_documents({'role': 'patient'})
        doctors_count = mongo.db.users.count_documents({'role': 'doctor'})
        appointments_count = mongo.db.appointments.count_documents({})

        # Fetch all users
        users = list(mongo.db.users.find())
        
        # Fetch unverified doctors
        unverified_doctors = list(mongo.db.users.find({'role': 'doctor', 'verified': False}))
        
        # Fetch verified doctors
        verified_doctors = list(mongo.db.users.find({'role': 'doctor', 'verified': True}))

        return render_template(
            'admin_dashboard.html',
            patients_count=patients_count,
            doctors_count=doctors_count,
            appointments_count=appointments_count,
            users=users,
            unverified_doctors=unverified_doctors,
            verified_doctors=verified_doctors
        )
    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))

# Other dashboards (Patient & Doctor)
@app.route('/patient_dashboard')
def patient_dashboard():
    if 'user_id' in session and session.get('role') == 'patient':
        appointments = list(mongo.db.appointments.find({'patient_id': ObjectId(session['user_id'])}))
        return render_template('patient_dashboard.html', appointments=appointments)
    return redirect(url_for('login'))

@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'user_id' in session and session['role'] == 'doctor':
        doctor_id = ObjectId(session['user_id'])
        appointments = list(mongo.db.appointments.find({"doctor_id": doctor_id}))
        return render_template('doctor_dashboard.html', appointments=appointments)
    return redirect(url_for('login'))

@app.route('/create_appointment', methods=['GET', 'POST'])
def create_appointment():
    if 'user_id' in session and session.get('role') == 'patient':
        if request.method == 'POST':
            # Get form data
            patient_name = request.form['patient_name']
            doctor_id = request.form['doctor_id']  # This will be the ObjectId of the doctor
            age = request.form['age']
            phone = request.form['phone']
            height = request.form['height']
            weight = request.form['weight']
            cause = request.form['cause']
            appointment_datetime = request.form['appointment_datetime']
            email = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})['email']
            
            # File upload (optional)
            report = request.files['report']
            filename = None
            if report and allowed_file(report.filename):
                filename = secure_filename(report.filename)
                report.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Find the doctor's name to include in the flash message
            doctor = mongo.db.users.find_one({'_id': ObjectId(doctor_id)})
            doctor_name = f"{doctor['first_name']} {doctor['last_name']}"

            # Insert appointment into database
            mongo.db.appointments.insert_one({
                'patient_name': patient_name,
                'doctor_id': ObjectId(doctor_id),
                'age': age,
                'phone': phone,
                'email': email,
                'height': height,
                'weight': weight,
                'cause': cause,
                'appointment_datetime': appointment_datetime,
                'report': filename,
                'patient_id': ObjectId(session['user_id']),
                'status': 'pending'
            })

            # Flash message with doctor name
            flash(f"Appointment created successfully with Dr. {doctor_name}!", "success")
            return redirect(url_for('patient_dashboard'))

        # Fetch doctors from the database for selection
        doctors = list(mongo.db.users.find({'role': 'doctor'}))
        return render_template('create_appointment.html', doctors=doctors)
    
    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
