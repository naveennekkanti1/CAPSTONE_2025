from flask import Flask, render_template, request, redirect, url_for, session, flash, url_for,send_file,jsonify,Response
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId,errors
from werkzeug.utils import secure_filename
from datetime import datetime,timedelta
from pymongo import MongoClient,DESCENDING
import base64
import io,random
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from flask_mail import Mail, Message
import gridfs,logging
import threading
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
import uuid,smtplib



app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['MONGO_URI'] = app.config['MONGO_URI'] = "mongodb+srv://durganaveen:nekkanti@cluster0.8nibi9x.mongodb.net/RAPACT?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(app.config['MONGO_URI'])
db = client['RAPACT']
users_collection = db['users']
appointments_collection = db['appointments']
meetings_collection=db['meetings']
enquiry_collection=db['enquiry_details']
fs = gridfs.GridFS(db)
SCOPES = ["https://www.googleapis.com/auth/calendar"]

#Flask-Mail Sending
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'srmcorporationservices@gmail.com'
app.config['MAIL_PASSWORD'] = 'bxxo qcvd njfj kcsa'
app.config['MAIL_DEFAULT_SENDER'] = 'srmcorporationservices@gmail.com'
otp_store = {}  
mail = Mail(app)

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

def send_email(subject, recipients, body):
    """Function to send emails."""
    try:
        msg = Message(subject, recipients=recipients, body=body)
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

def schedule_email(subject, recipients, body, send_time):
    """Schedule an email to be sent at a later time."""
    delay = (send_time - datetime.now()).total_seconds()
    if delay > 0:
        threading.Timer(delay, send_email, [subject, recipients, body]).start()
def get_google_credentials():
    creds = None
    token_path = 'token.json'  # Stores user's access token

    # Load existing credentials if available
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If no valid credentials, prompt login
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'templates/credentials.json', SCOPES)  # Use your OAuth 2.0 client secret
        creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return creds

def create_google_meet(patient_email, doctor_email, meeting_datetime):
    credentials = get_google_credentials()  # OAuth 2.0 authentication
    service = build('calendar', 'v3', credentials=credentials)

    event = {
        'summary': 'Doctor Consultation',
        'description': f'Meeting between {doctor_email} and {patient_email}',
        'start': {
            'dateTime': datetime.fromisoformat(meeting_datetime).isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': (datetime.fromisoformat(meeting_datetime) + timedelta(minutes=30)).isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'attendees': [
            {'email': doctor_email},  # Doctor email
            {'email': patient_email}  # Patient email
        ],
        'conferenceData': {
            'createRequest': {
                'requestId': str(uuid.uuid4()),
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        }
    }

    try:
        event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1
        ).execute()

        return event.get('hangoutLink')  # Return Google Meet link
    except Exception as e:
        print(f"Error creating Google Meet: {e}")
        return None


from datetime import datetime

@app.route('/schedule_meeting', methods=['GET', 'POST'])
def schedule_meeting():
    if 'user_id' in session and session['role'] in ['doctor', 'admin']:  
        doctor_id = ObjectId(session['user_id'])

        if request.method == 'POST':
            patient_id = ObjectId(request.form['patient_id'])
            meeting_datetime = request.form['meeting_datetime']

            # Validate if patient exists
            patient = mongo.db.users.find_one({'_id': patient_id}, {'name': 1, 'email': 1})
            if not patient or 'email' not in patient:
                flash("Selected patient does not exist or has no email.", "danger")
                return redirect(url_for('schedule_meeting'))

            patient_email = patient['email']

            # Validate if doctor exists
            doctor = mongo.db.users.find_one({'_id': doctor_id}, {'name':1, 'email': 1})
            if not doctor or 'email' not in doctor:
                flash("Doctor account issue: No email found.", "danger")
                return redirect(url_for('schedule_meeting'))

            doctor_email = doctor['email']

            # Generate Google Meet link
            try:
                meeting_link = create_google_meet(patient_email, doctor_email, meeting_datetime)
            except Exception as e:
                flash(f"Error creating Google Meet: {str(e)}", "danger")
                return redirect(url_for('schedule_meeting'))

            # Store the meeting details
            meeting_id = meeting_link.split('/')[-1]  # Extract Google Meet ID
            mongo.db.meetings.insert_one({
                'doctor_id': doctor_id,
                'patient_id': patient_id,
                'meeting_id': meeting_id,
                'meeting_datetime': meeting_datetime,
                'meeting_link': meeting_link
            })

            # Send email notification
            subject = "📅 Your Medical Appointment is Scheduled"
            body = f"""
        Dear {patient['name']},

        Your meeting with Dr. {doctor['name']} has been scheduled.

        📅 Date & Time: {meeting_datetime}
        🔗 Join Here: {meeting_link}

        Please ensure you join on time.

        Regards,
        RapiACT! Team ❤️
        """
            send_email(subject, [patient_email], body)

            flash("Meeting scheduled successfully!", "success")
            return redirect(url_for('schedule_meeting'))

        # Fetch all patients for dropdown selection
        patients = list(mongo.db.users.find({'role': 'patient'}, {'_id': 1,'name': 1}))

        # Fetch all scheduled meetings for the logged-in doctor
        meetings = list(mongo.db.meetings.find({'doctor_id': doctor_id}))

        # Separate meetings into ongoing, upcoming, and past
        ongoing_meetings = []
        upcoming_meetings = []
        past_meetings = []
        current_time = datetime.utcnow()

        for meeting in meetings:
            patient = mongo.db.users.find_one({'_id': meeting['patient_id']}, {'name': 1})
            meeting['patient_name'] = f"{patient['name']}" if patient else "Unknown"

            meeting_time = datetime.strptime(meeting['meeting_datetime'], "%Y-%m-%dT%H:%M")
            
            # Check if meeting is ongoing (within a 1-hour window)
            if meeting_time <= current_time <= meeting_time.replace(hour=meeting_time.hour + 1):
                ongoing_meetings.append(meeting)
            elif meeting_time > current_time:
                upcoming_meetings.append(meeting)
            else:
                past_meetings.append(meeting)

        return render_template('schedule_meeting.html', 
                               patients=patients, 
                               ongoing_meetings=ongoing_meetings, 
                               upcoming_meetings=upcoming_meetings, 
                               past_meetings=past_meetings)

    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))



def get_scheduled_meetings():
    meetings = db.meetings.find().sort("meeting_datetime", DESCENDING)
    
    meeting_list = []
    for meeting in meetings:
        meeting_list.append({
            "patient_name": f"{meeting.get('patient_name', '')}",
            "meeting_datetime": meetings.get("meeting_datetime", "Not Scheduled"),
            "meeting_link": meetings.get("meeting_link", "#")  # Default to "#" if link is missing
        })
    
    return meeting_list

@app.route('/join_meeting/<meeting_id>')
def join_meeting(meeting_id):
    if 'user_id' in session:
        meeting = mongo.db.meetings.find_one({"meeting_id": meeting_id})
        if meeting:
            return redirect(meeting['meeting_link'])  # Redirect to Google Meet
        flash("Meeting not found.", "danger")
        return redirect(url_for('patient_dashboard'))
    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    elif request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        role = data.get('role')

        if not email or not password or not confirm_password or not role:
            flash("All fields are required!", "danger")
            return redirect(url_for('register'))

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))

        if users_collection.find_one({"email": email}):
            flash("User already registered!", "danger")
            return redirect(url_for('register'))

        if email not in otp_store:
            flash("OTP not verified!", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        user_data = {
            "email": email,
            "password": hashed_password,
            "role": role,
            "created_at": datetime.utcnow()
        }
        users_collection.insert_one(user_data)
        del otp_store[email]

        flash("Registration successful!", "success")
        return redirect(url_for('login'))

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    if users_collection.find_one({"email": email}):
        return jsonify({"error": "User already registered!"}), 400

    otp = str(random.randint(100000, 999999))
    otp_store[email] = otp

    subject = "Your OTP Code"
    body = f"Hello,\n\nYour OTP code is: {otp}\n\nUse this code to complete your registration.\n\nThanks,\nRapiACT! Team"
    
    try:
        msg = Message(subject=subject, recipients=[email], body=body)
        mail.send(msg)
        return jsonify({"message": "OTP sent successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    otp_entered = data.get('otp')
    name = data.get('name')
    password = data.get('password')
    role = data.get('role')

    if not email or not otp_entered:
        return jsonify({"error": "Email and OTP are required"}), 400

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "User already registered!"}), 400  

    if email in otp_store and otp_store[email] == otp_entered:
        hashed_password = generate_password_hash(password)
        session.permanent = True  # Ensure session persists
        session["pending_user"] = {
            "name": name,
            "email": email,
            "password": hashed_password,
            "role": role
        }
        del otp_store[email]  # Remove OTP after successful verification

        return jsonify({"message": "OTP verified successfully!", "redirect_url": url_for('register')})

    return jsonify({"error": "Invalid OTP. Please try again!"}), 400


@app.route('/patient_register', methods=['GET', 'POST'])
def patient_register():
    if request.method == 'GET':
        return render_template('patient_register.html')

    elif request.method == 'POST':
        if "pending_user" not in session:
            return jsonify({"error": "No user session found. Please register again."}), 400

        data = request.form
        phone = data.get("phone")
        age = data.get("age")
        gender = data.get("gender")
        address = data.get("address")

        if not (phone and age and gender and address):
            return jsonify({"error": "All fields are required"}), 400

        # Get pending user details from session
        user_data = session["pending_user"]

        # Handle photo upload
        if 'photo' not in request.files:
            return jsonify({"error": "Photo is required"}), 400

        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({"error": "Invalid photo file"}), 400

        # Store photo in GridFS
        photo_id = fs.put(photo, filename=photo.filename)

        # Complete user data
        user_data.update({
            "role": "patient",
            "phone": phone,
            "age": age,
            "gender": gender,
            "address": address,
            "photo": photo_id,  # Store reference to photo in MongoDB
            "created_at": datetime.utcnow()
        })

        # Save user in MongoDB
        users_collection.insert_one(user_data)

        # Remove session data
        session.pop("pending_user", None)

        return jsonify({"message": "Registration successful!", "redirect_url": url_for('login')})

@app.route('/doctor_register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'GET':
        return render_template('doctor_register.html')

    elif request.method == 'POST':
        if "pending_user" not in session:
            return jsonify({"error": "No user session found. Please register again."}), 400

        data = request.form
        phone = data.get("phone")
        age = data.get("age")
        gender = data.get("gender")
        address = data.get("address")
        specialization = data.get("specialization")
        years_experience = data.get("experience")
        professional_experience = data.get("pro_experience", "")

        if not (phone and age and gender and specialization and years_experience and address):
            return jsonify({"error": "All fields are required."}), 400

        if 'photo' not in request.files:
            return jsonify({"error": "Photo is required"}), 400

        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({"error": "Invalid photo file"}), 400

        photo_id = fs.put(photo, filename=photo.filename)

        # Retrieve email from session
        pending_user = session["pending_user"]
        name=pending_user.get("name")
        email = pending_user.get("email")
        password = pending_user.get("password")

        if not email:
            return jsonify({"error": "Email is missing. Please register again."}), 400

        user_data = {
            "email": email,  # Ensure email is saved
            "password": password,  # Save hashed password
            "name":name,
            "role": "doctor",
            "phone": phone,
            "age": age,
            "gender": gender,
            "address": address,
            "specialization": specialization,
            "years_experience": years_experience,
            "professional_experience": professional_experience,
            "photo": photo_id,
            "created_at": datetime.utcnow(),
            "account_status": "pending"
        }

        users_collection.insert_one(user_data)

        # Remove session data after registration
        session.pop("pending_user", None)

        return jsonify({"message": "Registration successful! Await admin approval.", "redirect_url": url_for('login')})


# ---- Login ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    elif request.method == 'POST':
        data = request.form
        email = data.get("email")
        password = data.get("password")

        if not (email and password):
            flash("Email and password are required", "danger")
            return redirect(url_for('login'))

        user = users_collection.find_one({"email": email})

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid credentials", "danger")
            return redirect(url_for('login'))

        if user.get("role") == "doctor" and user.get("account_status") != "approved":
            flash("Your account is pending approval from the administrator.", "warning")
            return redirect(url_for('login'))

        session["user_id"] = str(user["_id"])
        session["role"] = user.get("role")

        flash("You have successfully logged in!", "success")
        return redirect(url_for('dashboard'))

# ---- Admin Dashboard ----
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    total_users = users_collection.count_documents({})
    total_doctors = users_collection.count_documents({'role': 'doctor'})
    total_patients = users_collection.count_documents({'role': 'patient'})
    total_appointments=appointments_collection.count_documents({})
    total_meetings=meetings_collection.count_documents({})
    total_enquires=enquiry_collection.count_documents({})

    unapproved_doctors = list(users_collection.find({'role': 'doctor', 'account_status': 'pending'},
                                                     {'_id': 1, 'name': 1, 'email': 1,'specialization':1,'years_experience':1,'professional_experience':1,'age':1,'gender':1}))

    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_doctors=total_doctors,
                           total_patients=total_patients,
                           total_appointments=total_appointments,
                           total_meetings=total_meetings,
                           total_enquires=total_enquires,
                           unapproved_doctors=unapproved_doctors)

# ---- Approve Doctor ----
@app.route('/approve_doctor/<doctor_id>', methods=['POST'])
def approve_doctor(doctor_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403

    doctor = users_collection.find_one({'_id': ObjectId(doctor_id)}, {'email': 1, 'name':1})

    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    if 'email' not in doctor:
        return jsonify({"error": "Doctor email missing in database"}), 400

    # Approve the doctor
    users_collection.update_one({'_id': ObjectId(doctor_id)}, {'$set': {'account_status': 'approved'}})

    subject = "Doctor Registration Approved"
    recipients = [doctor['email']]
    body = f"Hello {doctor.get('name', 'Doctor')},\n\nYour registration has been approved by the RapiACT Team!❤️. You can now log in.\n\nThanks,\nRapiACT! Team"

    send_email(subject, recipients, body)

    # Add email-sending functionality here if required

    return jsonify({"message": "Doctor approved successfully"})


@app.route('/reject_doctor/<doctor_id>', methods=['POST'])
def reject_doctor(doctor_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403

    doctor = users_collection.find_one({'_id': ObjectId(doctor_id)}, {'email': 1, 'name': 1})

    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    if 'email' not in doctor:
        return jsonify({"error": "Doctor email missing in database"}), 400

    # Delete the doctor from the database
    users_collection.delete_one({'_id': ObjectId(doctor_id)})

    subject = "Doctor Registration Rejected"
    recipients = [doctor['email']]
    body = f"Hello {doctor.get('name', 'Doctor')},\n\nWe regret to inform you that your registration with RapiACT has been rejected.\n\nFor any queries, feel free to contact us.\n\nThanks,\nRapiACT! Team"

    send_email(subject, recipients, body)

    return jsonify({"message": "Doctor rejected and removed successfully"})


@app.route('/user_photo/<user_id>')
def user_photo(user_id):
    try:
        # Ensure user_id is a valid ObjectId
        user_id = ObjectId(user_id)
    except errors.InvalidId:
        return send_file("static/images/logo.jpg", mimetype="image/png")  # Return default image if invalid ID

    user = db.users.find_one({"_id": user_id})
    
    if user and "photo" in user:
        try:
            image = fs.get(ObjectId(user["photo"]))  # Fetch image from GridFS
            return send_file(io.BytesIO(image.read()), mimetype="image/jpeg")
        except Exception as e:
            print(f"Error fetching image: {e}")
    
    return send_file("static/images/logo.jpg", mimetype="image/png")  # Default image if error


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
            appointment["doctor_name"] = doctor.get("name", "Unknown")
            appointment["doctor_specialization"] = doctor.get("specialization", "Unknown")
        else:
            appointment["doctor_name"] = "Unknown"
            appointment["doctor_specialization"] = "Unknown"
    
    return render_template('appointments.html', appointments=appointments)


@app.route('/patient_dashboard')
@app.route('/patient_dashboard/<appointment_type>')
def patient_dashboard(appointment_type=None):
    if 'user_id' not in session or session['role'] != 'patient':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    patient_id = ObjectId(session['user_id'])

    # Fetch patient details
    patient = mongo.db.users.find_one({'_id': patient_id}, {'name': 1})
    if not patient:
        flash("Patient record not found.", "danger")
        return redirect(url_for('login'))

    # Fetch patient's appointments and meetings
    appointments = list(mongo.db.appointments.find({"patient_id": patient_id}))
    meetings = list(mongo.db.meetings.find({"patient_id": patient_id}))

    # Fetch doctor details for each appointment
    for appointment in appointments:
        doctor = mongo.db.users.find_one({"_id": appointment["doctor_id"]}, {"name":1, "specialization": 1})
        if doctor:
            appointment["doctor_name"] = doctor.get("name")
            appointment["specialization"] = doctor.get("specialization")
        else:
            appointment["doctor_name"] = "Unknown"
            appointment["specialization"] = "Unknown"

    # Classify appointments
    upcoming_appointments, ongoing_appointments, completed_appointments = [], [], []
    current_time = datetime.utcnow()

    for appointment in appointments:
        try:
            appointment_time = datetime.strptime(appointment['appointment_datetime'], '%Y-%m-%dT%H:%M')
        except ValueError:
            flash("Invalid appointment date format.", "danger")
            continue

        if appointment.get("status") in ["done", "completed"]:
            completed_appointments.append(appointment)
        elif appointment_time > current_time:
            upcoming_appointments.append(appointment)
        else:
            ongoing_appointments.append(appointment)

    # Filter by `appointment_type`
    appointment_filters = {
        "upcoming": (upcoming_appointments, [], []),
        "ongoing": ([], ongoing_appointments, []),
        "completed": ([], [], completed_appointments)
    }

    filtered_appointments = appointment_filters.get(appointment_type, 
        (upcoming_appointments, ongoing_appointments, completed_appointments))

    return render_template(
        'patient_dashboard.html',
        name=patient.get('name', ''),
        upcoming_appointments=filtered_appointments[0],
        ongoing_appointments=filtered_appointments[1],
        completed_appointments=filtered_appointments[2],
        meetings=meetings
    )



def get_doctor_info():
    if 'user_id' in session and session['role'] == 'doctor':
        doctor_id = ObjectId(session['user_id'])
        doctor = mongo.db.users.find_one({'_id': doctor_id}, {'name': 1})
        return doctor
    return None

@app.route('/doctor_dashboard')
@app.route('/doctor_dashboard/<appointment_type>')
def doctor_dashboard(appointment_type=None):
    if 'user_id' in session and session['role'] == 'doctor':
        doctor_id = ObjectId(session['user_id'])
        doctor = get_doctor_info()
        
        if not doctor:
            flash("Doctor record not found.", "danger")
            return redirect(url_for('login'))
        
        appointments = list(mongo.db.appointments.find({"doctor_id": doctor_id}))
        upcoming_appointments = []
        ongoing_appointments = []
        completed_appointments = []
        current_time = datetime.now()
        
        for appointment in appointments:
            appointment_time = datetime.strptime(appointment['appointment_datetime'], '%Y-%m-%dT%H:%M')
            
            if appointment.get("status") in ["done", "completed"]:
                completed_appointments.append(appointment)
            elif appointment_time > current_time:
                upcoming_appointments.append(appointment)
            else:
                ongoing_appointments.append(appointment)
        
        # Filter based on appointment_type
        if appointment_type == "upcoming":
            return render_template('doctor_dashboard.html', doctor=doctor,
                                   upcoming_appointments=upcoming_appointments, 
                                   ongoing_appointments=[], 
                                   completed_appointments=[])
        elif appointment_type == "ongoing":
            return render_template('doctor_dashboard.html', doctor=doctor,
                                   upcoming_appointments=[], 
                                   ongoing_appointments=ongoing_appointments, 
                                   completed_appointments=[])
        elif appointment_type == "completed":
            return render_template('doctor_dashboard.html', doctor=doctor,
                                   upcoming_appointments=[], 
                                   ongoing_appointments=[], 
                                   completed_appointments=completed_appointments)
        
        # Default: Show all
        return render_template('doctor_dashboard.html', doctor=doctor,
                               upcoming_appointments=upcoming_appointments,
                               ongoing_appointments=ongoing_appointments,
                               completed_appointments=completed_appointments)
    return redirect(url_for('login'))



# Route to cancel an appointment
@app.route('/cancel_appointment/<appointment_id>', methods=['POST'])
def cancel_appointment(appointment_id):
    if 'user_id' in session:
        appointment = mongo.db.appointments.find_one({'_id': ObjectId(appointment_id)})
        if appointment and appointment['patient_id'] == ObjectId(session['user_id']):
            mongo.db.appointments.delete_one({'_id': ObjectId(appointment_id)})

            # Send cancellation email to patient
            email = appointment['email']
            subject = "Appointment Cancellation"
            body = f"Dear {appointment['patient_name']},\n\nYour appointment has been canceled.\n\nThank you!"
            send_email(subject, [email], body)

            flash("Appointment canceled successfully.", "success")
        else:
            flash("Unauthorized action.", "danger")

        return redirect(url_for('patient_dashboard'))
    return redirect(url_for('login'))


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
    feedback = request.form.get('feedback')
    if not feedback:
        return jsonify({"error": "Feedback cannot be empty"}), 400

    try:
        obj_id = ObjectId(appointment_id)
    except Exception:
        return jsonify({"error": "Invalid appointment ID"}), 400

    result = db.appointments.update_one({"_id": obj_id}, {"$set": {"feedback": feedback}})
    if result.modified_count == 0:
        return jsonify({"error": "Feedback not saved. Appointment not found."}), 400

    flash("Feedback submitted successfully!", "success")
    return redirect(url_for('doctor_dashboard'))


@app.route('/mark_as_done/<appointment_id>', methods=['POST'])
def mark_as_done(appointment_id):
    try:
        obj_id = ObjectId(appointment_id)
    except Exception:
        return jsonify({"error": "Invalid appointment ID"}), 400

    result = db.appointments.update_one({"_id": obj_id}, {"$set": {"status": "done"}})
    if result.modified_count == 0:
        return jsonify({"error": "Could not mark appointment as done"}), 400

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

# Creation of Appointment
@app.route('/create_appointment', methods=['GET', 'POST'])
def create_appointment():
    if 'user_id' in session and session.get('role') == 'patient':
        if request.method == 'POST':
            patient_name = request.form['patient_name']
            doctor_id = request.form['doctor_id']
            age = request.form['age']
            phone = request.form['phone']
            height = request.form['height']
            weight = request.form['weight']
            cause = request.form['cause']
            appointment_datetime = request.form['appointment_datetime']
            email = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})['email']

            # File upload (GridFS)
            report = request.files['report']
            file_id = None
            if report:
                file_id = fs.put(report, filename=secure_filename(report.filename), content_type=report.content_type)

            doctor = mongo.db.users.find_one({'_id': ObjectId(doctor_id)})
            doctor_name = f"{doctor['name']}"
            doctor_email = doctor['email']

            # Insert appointment into DB
            appointment_id = mongo.db.appointments.insert_one({
                'patient_name': patient_name,
                'doctor_id': ObjectId(doctor_id),
                'age': age,
                'phone': phone,
                'email': email,
                'height': height,
                'weight': weight,
                'cause': cause,
                'appointment_datetime': appointment_datetime,
                'report_id': file_id,
                'patient_id': ObjectId(session['user_id']),
            }).inserted_id

            # Email content
            subject = "Appointment Confirmation"
            body_patient = f"Dear {patient_name},\n\nYour appointment with Dr. {doctor_name} is confirmed on {appointment_datetime}.\n\nThank you!\n RapiACT!"
            body_doctor = f"Dear Dr. {doctor_name},\n\nYou have a new appointment with {patient_name} on {appointment_datetime}.\n\nThank you!\n RapiACT!"

            # Send emails
            send_email(subject, [email], body_patient)
            send_email(subject, [doctor_email], body_doctor)

            # Schedule reminder email
            appointment_time = datetime.strptime(appointment_datetime, "%Y-%m-%dT%H:%M")
            reminder_time = appointment_time - timedelta(minutes=5)
            reminder_subject = "Appointment Reminder"
            reminder_body = f"Dear {patient_name},\n\nThis is a reminder that your appointment with Dr. {doctor_name} is in 5 minutes."
            schedule_email(reminder_subject, [email], reminder_body, reminder_time)

            flash(f"Appointment created successfully with Dr. {doctor_name}!", "success")
            return redirect(url_for('patient_dashboard'))

        doctors = list(mongo.db.users.find({'role': 'doctor'}))
        return render_template('create_appointment.html', doctors=doctors)

    flash("Unauthorized access.", "danger")
    return redirect(url_for('login'))


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form.get('name')
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
            "name": name,
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

        flash(f"User {name} registered successfully!", "success")
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
            'name': request.form['name'],
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


from bson.json_util import dumps

@app.route('/get_doctors', methods=['GET'])
def get_doctors():
    doctors = list(mongo.db.users.find({"role": "doctor"}))
    return dumps(doctors), 200, {'Content-Type': 'application/json'}


@app.route("/all_doctors")
def all_doctors():
    return render_template("all_doctors.html")

@app.route("/get_visitors")
def get_visitors():
    # Ensure the visitors collection exists
    visitor_data = mongo.db.visitors.find_one({})
    
    if not visitor_data:
        mongo.db.visitors.insert_one({"count": 1})  # Initialize if not present
        count = 1
    else:
        mongo.db.visitors.update_one({}, {"$inc": {"count": 1}})
        count = visitor_data["count"] + 1  # Predict the updated count
    
    return jsonify({"count": count})

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
