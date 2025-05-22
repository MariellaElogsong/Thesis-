from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    message = "This message is generated from Python!"
    return render_template('index.html', message=message)

if __name__ == "__main__":
    app.run(debug=True)