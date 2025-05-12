from flask import Flask, render_template, request
import os
import pandas as pd
import re
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['excel_file']
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            xls = pd.ExcelFile(filepath)
            sheets = [s for s in xls.sheet_names if s.lower() != "answer key"]
            return render_template('select_sheet.html', filename=file.filename, sheets=sheets)
    return render_template('index.html')

@app.route('/route_selector', methods=['POST'])
def route_selector():
    filename = request.form['filename']
    sheet = request.form['sheet']
    mode = request.form['view_mode']
    
    if mode == 'multi':
        return render_template('select_questions.html', filename=filename, sheet=sheet)
    else:
        return select_columns()

@app.route('/select_columns', methods=['POST'])
def select_columns():
    filename = request.form['filename']
    sheet = request.form['sheet']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    all_cols = df.columns.tolist()

    question_ids = set()
    for col in all_cols:
        match = re.search(r"(Q\d+)", col)
        if match:
            question_ids.add(match.group(1))
        else:
            question_ids.add(col.strip())

    def question_sort_key(q):
        match = re.match(r"Q(\d+)", q)
        return (0, int(match.group(1))) if match else (1, q.lower())

    columns = sorted(question_ids, key=question_sort_key)
    return render_template('select_columns.html', filename=filename, sheet=sheet, columns=columns)

@app.route('/get_answer_key_values', methods=['POST'])
def get_answer_key_values():
    filename = request.form['filename']
    question = request.form['question']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    values = []
    capture = False
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and str(row[0]).strip() == question.strip():
            capture = True
            continue
        if capture and pd.isna(row[0]):
            break
        if capture and pd.notna(row[1]):
            values.append(str(row[1]).strip())

    return json.dumps(values)

@app.route('/select_questions', methods=['POST'])
def select_questions():
    filename = request.form['filename']
    sheet = request.form['sheet']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    questions = []
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and pd.isna(row[1]):
            questions.append(str(row[0]).strip())

    return render_template(
        'select_questions.html',
        filename=filename,
        sheet=sheet,
        questions=questions
    )

# Register routes
from routes.single_choice import register_single_choice_routes
from routes.matrix_question import register_matrix_question_routes
from routes.multiple_select import register_multiple_select_routes
from routes.cross_cut import register_cross_cut_routes
from routes.rank_based import register_ranked_question_routes
from routes.nps_question import register_nps_question_routes

register_nps_question_routes(app)
register_ranked_question_routes(app)
register_single_choice_routes(app)
register_matrix_question_routes(app)
register_multiple_select_routes(app)
register_cross_cut_routes(app)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
