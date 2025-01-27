from werkzeug.security import generate_password_hash

new_password = "admin"  # the new password you want to set
hashed_password = generate_password_hash(new_password)
print(hashed_password)
