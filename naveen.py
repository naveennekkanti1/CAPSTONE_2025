import re
import textract

def extract_liver_report_data(file_path):
    # Extract text from PDF using textract
    try:
        text = textract.process(file_path, method='tesseract')
        text = text.decode('utf-8')  # Decode bytes to string
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

    # Dictionary to store extracted data
    extracted_data = {}

    # Define patterns for test names and their values
    patterns = {
        "AST (SGOT)": r"AST \(SGOT\):?\s*([<>]?\d+\.?\d*\s*U/L)",
        "ALT (SGPT)": r"ALT \(SGPT\):?\s*([<>]?\d+\.?\d*\s*U/L)",
        "AST:ALT Ratio": r"AST:ALT Ratio:?\s*(\d+\.?\d*)",
        "GGTP": r"GGTP:?\s*([<>]?\d+\.?\d*\s*U/L)",
        "Alkaline Phosphatase (ALP)": r"Alkaline Phosphatase \(ALP\):?\s*([<>]?\d+\.?\d*\s*U/L)",
        "Bilirubin Total": r"Bilirubin Total:?\s*([<>]?\d+\.?\d*\s*mg/dL)",
        "Bilirubin Direct": r"Bilirubin Direct:?\s*([<>]?\d+\.?\d*\s*mg/dL)",
        "Bilirubin Indirect": r"Bilirubin Indirect:?\s*([<>]?\d+\.?\d*\s*mg/dL)",
        "Total Protein": r"Total Protein:?\s*([<>]?\d+\.?\d*\s*g/dL)",
        "Albumin": r"Albumin:?\s*([<>]?\d+\.?\d*\s*g/dL)",
        "A : G Ratio": r"A : G Ratio:?\s*([<>]?\d+\.?\d*)"
    }

    # Search for patterns and extract data
    for test_name, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            extracted_data[test_name] = match.group(1)
        else:
            extracted_data[test_name] = "Not Found"

    return extracted_data


# Specify the path to your PDF file
file_path = "C:\Users\ndurg\Downloads\healthcare_app_project\static\uploads\liver.pdf"

# Extract data from the report
extracted_data = extract_liver_report_data(file_path)

# Print the extracted data
if extracted_data:
    print("Extracted Data:")
    for key, value in extracted_data.items():
        print(f"{key}: {value}")