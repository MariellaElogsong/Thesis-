from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    message = "This message is generated from Python!"
    return render_template('index.html', message=message)

@app.route('/result')
def result():
    return render_template('result.html')

if __name__ == "__main__":
    app.run(debug=True)