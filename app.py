from flask import Flask, render_template, request, redirect, url_for, session, flash, url_for,send_file,jsonify,Response
from flask_pymongo import PyMongo
from datetime import datetime,timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from werkzeug.utils import secure_filename
from datetime import datetime
from pymongo import MongoClient
import base64
import io
import os
import gridfs

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['MONGO_URI'] = app.config['MONGO_URI'] = "mongodb+srv://durganaveen:nekkanti@cluster0.8nibi9x.mongodb.net/RAPACT?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(app.config['MONGO_URI'])
db = client['RAPACT']
users_collection = db['users']
fs = gridfs.GridFS(db)

# File upload settings
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png'}

mongo = PyMongo(app)

# Ensure upload folder exists

# File type check function
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Home route
@app.route('/')
def home():
    user_logged_in = 'user_id' in session
    return render_template('index.html', user_logged_in=user_logged_in)


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/submit_enquiry', methods=['POST'])
def submit_enquiry():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    if name and email and message:
        mongo.db.enquiry_details.insert_one({
            "name": name,
            "email": email,
            "message": message,
            "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })
        return redirect('/')  # Redirect to home page after submission

    return "Failed to submit enquiry", 400


@app.route("/enquiry_details")
def get_enquiry_details():
    """ Fetch all enquiries from MongoDB sorted by newest first. """
    enquiries = list(mongo.db.enquiry_details.find().sort("date", -1))

    for enquiry in enquiries:
        if 'date' in enquiry and isinstance(enquiry['date'], str):
            try:
                enquiry['date'] = datetime.strptime(enquiry['date'], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                enquiry['date'] = None

    return render_template("enquiry_details.html", enquiries=enquiries)



@app.route("/mark_done", methods=["POST"])
def mark_done():
    """ Mark an enquiry as done and save the admin's response. """
    data = request.json
    enquiry_id = data.get("enquiry_id")
    response_text = data.get("response")

    if not enquiry_id or not response_text:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    try:
        result = mongo.db.enquiry_details.update_one(
            {"_id": ObjectId(enquiry_id)},  # Convert to ObjectId
            {"$set": {"status": "done", "response": response_text, "response_date": datetime.utcnow()}}
        )

        if result.modified_count == 1:
            return jsonify({"success": True, "message": "Enquiry marked as done."})
        else:
            return jsonify({"success": False, "message": "Failed to update enquiry."}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500




# Register Patient Route
@app.route('/register_patient', methods=['GET', 'POST'])
def register_patient():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phno=request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        house_no = request.form['house_no']
        village_city = request.form['village_city']
        district = request.form['district']
        state = request.form['state']
        photo = request.files['photo']

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register_patient'))

        if not allowed_file(photo.filename):
            flash("Invalid file type. Only PDF, JPG, JPEG, or PNG files are allowed.", "danger")
            return redirect(url_for('register_patient'))

        photo_data = base64.b64encode(photo.read()).decode('utf-8')

        if mongo.db.users.find_one({'email': email}):
            flash("Email already registered. Please use a different email.", "danger")
            return redirect(url_for('register_patient'))

        hashed_password = generate_password_hash(password)

        mongo.db.users.insert_one({
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone':phno,
            'password': hashed_password,
            'role': 'patient',
            'photo': photo_data,
            'house_no': house_no,
            'village_city': village_city,
            'district': district,
            'state': state
        })

        return redirect(url_for('login'))

    return render_template('patient_register.html')

@app.route('/user_photo/<user_id>')
def user_photo(user_id):
    user = db.users.find_one({"_id": ObjectId(user_id)})
    
    if user and "photo" in user:
        image_data = base64.b64decode(user["photo"])  # Convert Base64 string to bytes
        return send_file(io.BytesIO(image_data), mimetype="image/jpeg")
    
    return send_file("static/images/logo.jpg", mimetype="image/png")



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

        # Validate photo upload and convert to base64
        photo_data = None
        if photo and allowed_file(photo.filename):
            photo_data = base64.b64encode(photo.read()).decode('utf-8')
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
            'role': 'doctor',
            'photo': photo_data,  # Store as base64 string
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
        try:
            mongo.db["users"].insert_one(doctor_data)
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Database error: {str(e)}", "danger")
            return redirect(url_for('register_doctor'))

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
            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            flash("Login successful!", "success")
            return redirect(url_for('dashboard') + "?login_success=1")  # ✅ Redirect with success flag
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for('login') + "?login_failed=1")  # ❌ Redirect with error flag

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
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    # Fetch all users with their uploaded files
    users = list(mongo.db.users.find({}))

    # Counting total users, doctors, patients, and appointments
    total_users = mongo.db.users.count_documents({})
    total_doctors = mongo.db.users.count_documents({'role': 'doctor'})
    total_patients = mongo.db.users.count_documents({'role': 'patient'})
    total_appointments = mongo.db.appointments.count_documents({})

    # Counting appointment statuses
    upcoming_appointments = mongo.db.appointments.count_documents({"status": "upcoming"})
    completed_appointments = mongo.db.appointments.count_documents({"status": "completed"})
    cancelled_appointments = mongo.db.appointments.count_documents({"status": "cancelled"})

    return render_template('admin_dashboard.html',
                           users=users,
                           total_users=total_users,
                           total_doctors=total_doctors,
                           total_patients=total_patients,
                           total_appointments=total_appointments,
                           upcoming_appointments=upcoming_appointments,
                           completed_appointments=completed_appointments,
                           cancelled_appointments=cancelled_appointments)

@app.route('/users')
def users():
    role = request.args.get('role')
    query = {"role": role} if role else {}

    users = list(mongo.db.users.find(query))
    
    # Convert ObjectId to string for frontend display
    for user in users:
        user['_id'] = str(user['_id']) 

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
    if 'user_id' in session and session['role'] == 'patient':
        patient_id = ObjectId(session['user_id'])

        # Fetch patient details (first name and last name)
        patient = mongo.db.users.find_one({'_id': patient_id}, {'first_name': 1, 'last_name': 1})
        if not patient:
            flash("Patient record not found.", "danger")
            return redirect(url_for('login'))

        # Fetch patient's appointments
        appointments = list(mongo.db.appointments.find({"patient_id": patient_id}))
        meetings = list(mongo.db.meetings.find({"patient_id": patient_id}))

        # Classify appointments into upcoming and ongoing
        upcoming_appointments = []
        ongoing_appointments = []
        current_time = datetime.utcnow()

        for appointment in appointments:
            appointment_time = datetime.strptime(appointment['appointment_datetime'], '%Y-%m-%dT%H:%M')
            if appointment_time > current_time:
                upcoming_appointments.append(appointment)
            else:
                ongoing_appointments.append(appointment)

        return render_template('patient_dashboard.html',
                               first_name=patient.get('first_name', ''),
                               last_name=patient.get('last_name', ''),
                               upcoming_appointments=upcoming_appointments,
                               ongoing_appointments=ongoing_appointments,
                               meetings=meetings)

    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))


@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'user_id' in session and session['role'] == 'doctor':
        doctor_id = ObjectId(session['user_id'])
        appointments = list(mongo.db.appointments.find({"doctor_id": doctor_id}))

        # Classify appointments into upcoming and ongoing
        upcoming_appointments = []
        ongoing_appointments = []
        current_time = datetime.now()

        for appointment in appointments:
            appointment_time = datetime.strptime(appointment['appointment_datetime'], '%Y-%m-%dT%H:%M')
            if appointment_time > current_time:
                upcoming_appointments.append(appointment)
            else:
                ongoing_appointments.append(appointment)

        return render_template('doctor_dashboard.html', 
                               upcoming_appointments=upcoming_appointments,
                               ongoing_appointments=ongoing_appointments)
    return redirect(url_for('login'))



# Route to cancel an appointment
@app.route('/cancel_appointment/<appointment_id>', methods=['POST'])
def cancel_appointment(appointment_id):
    if 'user_id' not in session or session.get('role') != 'patient':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    try:
        mongo.db.appointments.delete_one({'_id': ObjectId(appointment_id)})
        flash("Appointment canceled successfully.", "success")
    except Exception as e:
        flash(f"Error canceling appointment: {str(e)}", "danger")

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

@app.route('/give_feedback/<appointment_id>', methods=['POST'])
def give_feedback(appointment_id):
    feedback = request.form.get('feedback')  # Get feedback from form
    if not feedback:
        return jsonify({"error": "Feedback cannot be empty"}), 400
    
    mongo.db.appointments.update_one({"_id": ObjectId(appointment_id)}, {"$set": {"feedback": feedback}})
    flash("Feedback submitted successfully!", "success")
    return redirect(url_for('doctor_dashboard'))


@app.route('/mark_done/<appointment_id>', methods=['POST'])
def mark_done_for(appointment_id):
    try:
        # Ensure appointment_id is valid
        appointment_id = ObjectId(appointment_id)
    except Exception:
        return jsonify({"error": "Invalid appointment ID"}), 400

    # Update the appointment status
    result = mongo.db.appointments.update_one(
        {"_id": appointment_id}, 
        {"$set": {"status": "completed"}}
    )

    if result.matched_count == 0:
        flash("Appointment not found.", "danger")
        return redirect(url_for('doctor_dashboard'))

    flash("Appointment marked as done!", "success")
    return redirect(url_for('doctor_dashboard'))


@app.route('/get_report/<file_id>')
def get_report(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return Response(file.read(), mimetype=file.content_type, headers={"Content-Disposition": f"inline; filename={file.filename}"})
    except:
        flash("File not found.", "danger")
        return redirect(url_for('doctor_dashboard'))

@app.route('/schedule_meeting', methods=['GET', 'POST'])
def schedule_meeting():
    if 'user_id' in session and session['role'] == 'doctor':
        doctor_id = ObjectId(session['user_id'])

        if request.method == 'POST':
            patient_id = ObjectId(request.form['patient_id'])
            meeting_id = request.form['meeting_id']
            meeting_datetime = request.form['meeting_datetime']

            # Validate if patient exists
            patient = mongo.db.users.find_one({'_id': patient_id})
            if not patient:
                flash("Selected patient does not exist.", "danger")
                return redirect(url_for('schedule_meeting'))

            # Store the meeting details
            mongo.db.meetings.insert_one({
                'doctor_id': doctor_id,
                'patient_id': patient_id,
                'meeting_id': meeting_id,
                'meeting_datetime': meeting_datetime
            })

            flash("Meeting scheduled successfully!", "success")
            return redirect(url_for('doctor_dashboard'))

        # Fetch all patients for dropdown selection
        patients = mongo.db.users.find({'role': 'patient'}, {'_id': 1, 'first_name': 1, 'last_name': 1})
        return render_template('schedule_meeting.html', patients=patients)

    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))
@app.route('/join_meeting/<meeting_id>')
def join_meeting(meeting_id):
    if 'user_id' in session:
        meeting = mongo.db.meetings.find_one({"meeting_id": meeting_id})
        if meeting:
            return redirect(f"https://your-video-platform.com/{meeting_id}")  # Replace with your meeting service
        flash("Meeting not found.", "danger")
        return redirect(url_for('patient_dashboard'))
    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))

# Creation of Appointment
@app.route('/create_appointment', methods=['GET', 'POST'])
def create_appointment():
    if 'user_id' in session and session.get('role') == 'patient':
        if request.method == 'POST':
            # Get form data
            patient_name = request.form['patient_name']
            doctor_id = request.form['doctor_id']
            age = request.form['age']
            phone = request.form['phone']
            height = request.form['height']
            weight = request.form['weight']
            cause = request.form['cause']
            appointment_datetime = request.form['appointment_datetime']
            email = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})['email']

            # File upload (store in GridFS)
            report = request.files['report']
            file_id = None
            if report:
                file_id = fs.put(report, filename=secure_filename(report.filename), content_type=report.content_type)

            # Find the doctor's name to include in the flash message
            doctor = mongo.db.users.find_one({'_id': ObjectId(doctor_id)})
            doctor_name = f"{doctor['first_name']} {doctor['last_name']}"

            # Insert appointment into the database
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
                'report_id': file_id,  # Store the file ID from GridFS
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

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')

        # Password confirmation check
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('add_user'))

        # Handle file upload (convert to Base64)
        photo_data = None
        photo = request.files.get('photo')
        if photo and allowed_file(photo.filename):
            photo_data = base64.b64encode(photo.read()).decode('utf-8')
        elif photo and photo.filename != '':
            flash("Invalid file type. Only PDF, JPG, JPEG, or PNG files are allowed.", "danger")
            return redirect(url_for('add_user'))
        hashed_password = generate_password_hash(password)
        # Common user data
        user_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": hashed_password,
            "role": role,
            "photo_data": photo_data
        }

        # Additional fields for patients
        if role == 'patient':
            user_data.update({
                "phone": request.form.get('phone'),
                "house_no": request.form.get('house_no'),
                "village_city": request.form.get('village_city'),
                "district": request.form.get('district'),
                "state": request.form.get('state')
            })

        # Additional fields for doctors
        elif role == 'doctor':
            user_data.update({
                "age": request.form.get('age'),
                "gender": request.form.get('gender'),
                "phone": request.form.get('phone'),
                "experience_years": request.form.get('experience_years'),
                "specialization": request.form.get('specialization'),
                "brief_experience": request.form.get('brief_experience'),
                "house_no": request.form.get('house_no'),
                "city": request.form.get('city'),
                "state": request.form.get('state'),
                "country": request.form.get('country'),
                "pincode": request.form.get('pincode')
            })

        # Insert data into MongoDB
        users_collection.insert_one(user_data)

        flash(f"User {first_name} {last_name} registered successfully!", "success")
        return redirect(url_for('add_user'))

    return render_template('add_user.html')

def get_user_by_id(user_id):
    return users_collection.find_one({"_id": user_id})

def update_user(user_id, updated_data):
    users_collection.update_one({"_id": user_id}, {"$set": updated_data})

@app.route('/edit_user/<user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    # Fetch user from database using the user_id (converted to ObjectId)
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('users'))  # Redirect if user is not found

    if request.method == 'POST':
        # Extracting updated data from the form
        updated_data = {
            'first_name': request.form['first_name'],
            'last_name': request.form['last_name'],
            'email': request.form['email'],
            'role': request.form['role'],
        }
        
        # Update role-specific fields
        if updated_data['role'] == 'patient':
            updated_data.update({
                'house_no': request.form.get('house_no'),
                'village_city': request.form.get('village_city'),
                'district': request.form.get('district'),
                'state': request.form.get('state'),
            })
        elif updated_data['role'] == 'doctor':
            updated_data.update({
                'specialization': request.form.get('specialization'),
                'experience_years': request.form.get('experience_years'),
            })

        # Update the database
        mongo.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updated_data})
        flash("User updated successfully!", "success")
        return redirect(url_for('users'))

    return render_template('edit_user.html', user=user)


@app.route("/get_doctors")
def get_doctors():
    doctors = list(users_collection.find(
        {"role": "doctor"},  # Fetch only users with role "doctor"
        {"_id": 0, "first_name": 1, "last_name": 1, "specialization": 1, "photo": 1, "experience_years":1}
    ))
    return jsonify(doctors)

@app.route("/all_doctors")
def all_doctors():
    return render_template("all_doctors.html")

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
