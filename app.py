from flask import Flask, request, jsonify, render_template
import os
import pandas as pd
import re
import json

# Import processing functions instead of route registration
from routes.single_choice import process_single_choice
from routes.matrix_question import process_matrix_question
from routes.multiple_select import process_multi_select
from routes.cross_cut import process_cross_cut
from routes.rank_based import process_ranked_question
from routes.nps_question import process_nps_question

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
        return render_template('select_columns.html', filename=filename, sheet=sheet, columns=[])
    else:
        return select_columns()

@app.route('/select_columns', methods=['POST'])
def select_columns():
    filename = request.form['filename']
    sheet = request.form['sheet']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    data_columns = set()
    for col in df.columns:
        if isinstance(col, str):
            match = re.search(r"(Q\d+)", col)
            if match:
                data_columns.add(match.group(1))

    question_map = {}
    for _, row in df_key.iterrows():
        if pd.notna(row[0]) and pd.notna(row[1]):
            qid_match = re.match(r"(Q\d+)", str(row[0]).strip())
            if qid_match:
                question_map[qid_match.group(1)] = str(row[1]).strip()

    columns = sorted(data_columns.intersection(set(question_map.keys())), key=lambda q: int(q[1:]))
    question_pairs = [(qid, question_map[qid]) for qid in columns]

    return render_template('select_columns.html', filename=filename, sheet=sheet, question_pairs=question_pairs)

@app.route('/compare_multi_questions', methods=['POST'])
def compare_multi_questions():
    filename = request.form['filename']
    sheet = request.form['sheet']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    questions = [key.replace("include_", "") for key in request.form.keys() if key.startswith("include_")]

    results = []
    for q in questions:
        types = request.form.getlist(f"type_{q}")
        for q_type in types:
            cut_col = request.form.get(f'cut_column_{q}') or ''
            max_rank = request.form.get(f'max_rank_{q}') or ''

            filters = {
                'filter_questions': request.form.getlist('filter_question'),
                'filter_values': request.form.getlist('filter_value'),
                'cut_column': cut_col,
                'max_rank': max_rank
            }

            try:
                if q_type == 'cross_cut' and cut_col:
                    html = process_cross_cut(filepath, sheet, q, filters)
                    question_text = None  # suppress question text in header for cross cut
                elif q_type == 'single_choice':
                    html = process_single_choice(filepath, sheet, q, filters)
                elif q_type == 'matrix':
                    html = process_matrix_question(filepath, sheet, q, filters)
                elif q_type == 'multi_select':
                    html = process_multi_select(filepath, sheet, q, filters)
                elif q_type == 'ranked':
                    filters['max_rank'] = max_rank
                    html = process_ranked_question(filepath, sheet, q, filters)
                elif q_type == 'nps':
                    html = process_nps_question(filepath, sheet, q, filters)
                else:
                    html = f"<p>Unsupported or incomplete type for {q}</p>"

                if q_type != 'cross_cut':
                    question_text = None
                    for _, row in df_key.iterrows():
                        if str(row[0]).strip() == q and pd.notna(row[1]):
                            question_text = str(row[1]).strip()
                            break

                results.append({'question': q, 'text': question_text, 'html': html})

            except Exception as e:
                html = f"<p>Error processing {q} ({q_type}): {str(e)}</p>"
                question_text = f"{q} - {q_type}"
                results.append({'question': q, 'text': question_text, 'html': html})

    results.sort(key=lambda r: int(r['question'][1:]) if r['question'].startswith('Q') else 999)
    all_columns = sorted({row['question'] for row in results})
    return render_template('display_multi_results.html', results=results, filename=filename, sheet=sheet,all_columns = all_columns)

@app.route("/get_answer_key_values", methods=["POST"])
def get_answer_key_values():
    import os
    from flask import request, jsonify
    import pandas as pd

    filename = request.form.get("filename")
    question = request.form.get("question")

    if not filename or not question:
        return jsonify([])

    try:
        filepath = os.path.join("uploads", filename)
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

        values = []
        capture = False

        for _, row in df_key.iterrows():
            cell_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            cell_b = str(row[1]).strip() if pd.notna(row[1]) else ""

            if cell_a == question:
                capture = True
                continue

            if capture and cell_a.startswith("Q"):  # next question block
                break

            if capture and cell_b:
                values.append(cell_b)

        return jsonify(values)

    except Exception as e:
        print("Error in get_answer_key_values:", e)
        return jsonify([])

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)