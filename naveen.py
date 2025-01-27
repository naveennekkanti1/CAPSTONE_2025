from werkzeug.security import check_password_hash

# Example of a stored hashed password (this would be retrieved from your database)
stored_hashed_password = "scrypt:32768:8:1$0Kbu9OxL0W3Lynpp$f7b808d6fa54361e2fe104a09fad8bd7b45f321fa66d058d41c2d200255d51d94fa14a8c56982495d4feadaf600dd60180c95bea30e9ca290336a48be51e424e"

# The password entered by the user for verification
entered_password = "Preetham@123"

# Verifying the entered password against the stored hash
if check_password_hash(stored_hashed_password, entered_password):
    print("Password is correct!")
else:
    print("Incorrect password.")
