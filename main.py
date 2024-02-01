'''
This is the main file of the educational platform.
'''
from flask import Flask, render_template, request, redirect, url_for
from exercise import Exercise
from database import Database
from evaluator import Evaluator
app = Flask(__name__)
exercise = Exercise()
database = Database()
evaluator = Evaluator()
@app.route('/')
def index():
    evaluated_response = request.args.get('evaluated_response')
    return render_template('index.html', prompt=exercise.get_prompt(), evaluated_response=evaluated_response)
@app.route('/submit', methods=['POST'])
def submit():
    response = request.form['response']
    database.save_interaction(response)
    evaluated_response = evaluator.evaluate(response)
    return redirect(url_for('index', evaluated_response=evaluated_response))
if __name__ == '__main__':
    app.run()