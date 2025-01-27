from flask import Flask, render_template, request, redirect, url_for, session, flash, url_for
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from werkzeug.utils import secure_filename
from datetime import datetime
from pymongo import MongoClient

import os


app = Flask(__name__)
app.config['MONGO_URI'] = "mongodb://localhost:27017/RAPACT"
app.secret_key = 'your_secret_key'  # Used for session management

client = MongoClient("mongodb://localhost:27017/")
db = client['RAPACT']

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
        house_no = request.form['house_no']
        village_city = request.form['village_city']
        district = request.form['district']
        state = request.form['state']
        photo = request.files['photo']

        # Validate passwords
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register_patient'))

        # Handle file upload
        if photo and allowed_file(photo.filename):
            photo_filename = secure_filename(photo.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
            photo.save(photo_path)
        else:
            flash("Invalid file type. Only PDF, JPG, JPEG, or PNG files are allowed.", "danger")
            return redirect(url_for('register_patient'))

        # Check if email is already registered
        if mongo.db.users.find_one({'email': email}):
            flash("Email already registered. Please use a different email.", "danger")
            return redirect(url_for('register_patient'))

        # Hash password
        hashed_password = generate_password_hash(password)

        # Save user details to the database
        mongo.db.users.insert_one({
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': hashed_password,
            'role': 'patient',
            'photo': photo_filename,
            'house_no': house_no,
            'village_city': village_city,
            'district': district,
            'state': state
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
        photo = request.files['photo']

        # Validate passwords
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register_doctor'))

        # Validate photo upload
        photo_filename = None
        if photo and allowed_file(photo.filename):  # Ensure you define `allowed_file` function
            photo_filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        else:
            flash("Invalid file type. Only PDF, JPG, JPEG, or PNG files are allowed.", "danger")
            return redirect(url_for('register_doctor'))

        # Check if the email is already registered
        if mongo.db.users.find_one({'email': email}):
            flash("Email already registered. Please use a different email.", "danger")
            return redirect(url_for('register_doctor'))

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Doctor-specific fields
        doctor_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': hashed_password,
            'role': 'doctor',  # Hardcoded role
            'photo': photo_filename,
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
            }
        }

        # Insert the doctor data into the database
        mongo.db.users.insert_one(doctor_data)

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    # Render the doctor registration form
    return render_template('doctor_register.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        # Find the user by email and role
        user = mongo.db.users.find_one({'email': email, 'role': role})

        if user and check_password_hash(user['password'], password):
            # Remove verification check for doctors
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
# admin dashboard

@app.route('/admin_dashboard')
def admin_dashboard():
    total_users = db.users.count_documents({})
    total_doctors = db.users.count_documents({"role": "Doctor"})
    total_patients = db.users.count_documents({"role": "Patient"})
    total_appointments = db.appointments.count_documents({})

    return render_template(
        'admin_dashboard.html',
        total_users=total_users,
        total_doctors=total_doctors,
        total_patients=total_patients,
        total_appointments=total_appointments,
    )

@app.route('/users')
def users():
    role = request.args.get('role')
    if role:
        users = list(db.users.find({"role": role}))
    else:
        users = list(db.users.find())
    return render_template('users.html', users=users)




@app.route('/appointments')
def appointments():
    # Fetch appointments
    appointments = list(db.appointments.find())
    
    # Fetch doctor details and enrich appointments data
    for appointment in appointments:
        doctor = db.doctors.find_one({"_id": appointment["doctor_id"]})
        if doctor:
            appointment["doctor_name"] = doctor.get("first_name", "Unknown")
            appointment["doctor_specialization"] = doctor.get("specialization", "Unknown")
        else:
            appointment["doctor_name"] = "Unknown"
            appointment["doctor_specialization"] = "Unknown"
    
    return render_template('appointments.html', appointments=appointments)


@app.route('/patient_dashboard')
def patient_dashboard():
    if 'user_id' not in session or session.get('role') != 'patient':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for('login'))
    except Exception as e:
        flash(f"Error retrieving user details: {str(e)}", "danger")
        return redirect(url_for('login'))

    first_name = user.get('first_name', 'Unknown')
    last_name = user.get('last_name', 'Unknown')

    # Fetch appointments for the patient
    try:
        appointments = list(mongo.db.appointments.find({'patient_id': ObjectId(user_id)}))
        upcoming_appointments = []
        completed_appointments = []

        for appointment in appointments:
            doctor = mongo.db.doctors.find_one({'_id': ObjectId(appointment['doctor_id'])})
            if doctor:
                appointment['doctor_name'] = f"{doctor['first_name']} {doctor['last_name']}"
                appointment['specialization'] = doctor['specialization']
            
            # Convert appointment date to a proper datetime object if it's stored as a string
            appointment_datetime = appointment['appointment_datetime']
            if isinstance(appointment_datetime, str):
                appointment_datetime = datetime.strptime(appointment_datetime, "%Y-%m-%d %H:%M:%S")  # Adjust format accordingly

            appointment['appointment_datetime'] = appointment_datetime.strftime('%A, %d %B %Y, %I:%M %p')

            # Split appointments into upcoming and completed based on date comparison
            if appointment_datetime >= datetime.now():
                upcoming_appointments.append(appointment)
            else:
                completed_appointments.append(appointment)
    except Exception as e:
        flash(f"Error fetching appointments: {str(e)}", "danger")
        upcoming_appointments = []
        completed_appointments = []

    return render_template(
        'patient_dashboard.html',
        first_name=first_name,
        last_name=last_name,
        upcoming_appointments=upcoming_appointments,
        completed_appointments=completed_appointments
    )

@app.route('/completed/<appointment_id>', methods=['GET'])
def complete_appointment(appointment_id):
    if 'user_id' not in session or session.get('role') != 'patient':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    try:
        # Update the appointment status to 'completed'
        mongo.db.appointments.update_one(
            {'_id': ObjectId(appointment_id)},
            {'$set': {'status': 'completed'}}
        )
        flash("Appointment marked as completed.", "success")
    except Exception as e:
        flash(f"Error marking appointment as completed: {str(e)}", "danger")

    return redirect(url_for('patient_dashboard'))



@app.route('/profile')
def profile():
    # Assuming the user is logged in and their user_id is stored in session
    user_id = session.get('user_id')  # Modify as per your session handling
    
    if not user_id:
        return redirect(url_for('login'))  # Redirect to login page if not logged in
    
    try:
        # Fetch the user details using ObjectId
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})  # 'users' is the collection name
        
        if user:
            return render_template('profile.html', user=user)
        else:
            return "User not found", 404
    except Exception as e:
        return f"Error fetching user details: {str(e)}", 500

# Route for change password page
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        # Get the new password from the form
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('change_password'))
        
        user_id = session.get('user_id')
        
        if not user_id:
            return redirect(url_for('login'))  # Redirect to login page if not logged in
        
        # Hash the new password before saving it (consider using bcrypt or similar)
        hashed_password = generate_password_hash(new_password)
        
        # Update the user's password in MongoDB
        result = mongo.db.users.update_one(
            {"_id": user_id}, 
            {"$set": {"password": hashed_password}}
        )
        
        if result.matched_count > 0:
            flash('Password changed successfully!', 'success')
        else:
            flash('Error changing password. Please try again.', 'error')
        
        return redirect(url_for('profile'))
    
    return render_template('change_password.html')

# Route to update password

@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'user_id' in session and session['role'] == 'doctor':
        doctor_id = ObjectId(session['user_id'])
        appointments = list(mongo.db.appointments.find({"doctor_id": doctor_id}))
        return render_template('doctor_dashboard.html', appointments=appointments)
    return redirect(url_for('login'))

# Creation of Appointment
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
