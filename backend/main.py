from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os

app = Flask(__name__)

UPLOAD_FOLDER = 'current'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    message = "This message is generated from Python!"
    return render_template('index.html', message=message)

@app.route('/result')
def result():
    return render_template('result.html')

@app.route('/new')
def new():
    return render_template('new.html')

@app.route('/faculty')
def faculty():
    # Read the generated timetable
    timetable_path = 'final_timetable.csv'
    if os.path.exists(timetable_path):
        timetable_df = pd.read_csv(timetable_path)
        # Get unique instructor names, excluding 'Sample Instructor'
        instructors = sorted([
            name for name in timetable_df['Instructor'].unique()
            if name and name != 'Sample Instructor'
        ])
    else:
        instructors = []
    return render_template('faculty.html', instructors=instructors)

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('csvFile')
    allowed = {'instructors.csv', 'courses.csv', 'minorcourses.csv', 'rooms.csv'}
    for file in files:
        if file.filename in allowed:
            file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    # === Call your constraint programming logic here ===
    import constraint_programming  # Make sure this runs your logic and generates final_timetable.csv
    # ================================================
    return redirect(url_for('faculty'))

if __name__ == "__main__":
    app.run(debug=True)
