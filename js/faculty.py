# faculty.py
from flask import Flask, render_template
import pandas as pd

app = Flask(__name__)

@app.route('/faculty')
def faculty():
    df = pd.read_csv('Downloads/instructors.csv')  # Adjust path as needed
    instructors = df['InstructorName'].tolist()    # Use your CSV's column name
    return render_template('faculty.html', instructors=instructors)

if __name__ == '__main__':
    app.run(debug=True)