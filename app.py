from flask import Flask, request, jsonify, render_template
import os
import pandas as pd
import re
from copy import deepcopy

# Import processors for question types
from routes.single_choice import process_single_choice
from routes.matrix_question import process_matrix_question
from routes.multiple_select import process_multi_select
from routes.cross_cut import process_cross_cut
from routes.rank_based import process_ranked_question
from routes.nps_question import process_nps_question

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# -----------------------------------------
# Combined upload + sheet listing
# -----------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            xls = pd.ExcelFile(filepath)
            sheets = [s for s in xls.sheet_names if s.lower() != "answer key"]

            return jsonify({"success": True, "filename": filename, "sheets": sheets})
        return jsonify({"success": False, "error": "No file uploaded"})
    return render_template('index.html')


# -----------------------------------------
# Handles mode (single vs multi) after upload+sheet
# -----------------------------------------
@app.route('/route_selector', methods=['POST'])
def route_selector():
    filename = request.form['filename']
    sheet = request.form['sheet']
    return select_columns()


# -----------------------------------------
# Shows question list after selecting sheet
# -----------------------------------------
@app.route('/select_columns', methods=['POST'])
def select_columns():
    filename = request.form['filename']
    sheet = request.form['sheet']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    df = pd.read_excel(filepath, sheet_name=sheet, header=2)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    # Extract valid Q columns from the dataset
    data_columns = set()
    for col in df.columns:
        if isinstance(col, str):
            match = re.search(r"(Q\d+)", col)
            if match:
                data_columns.add(match.group(1))

    # Build question_map ONLY for questions with answer options
    question_map = {}
    i = 0
    while i < len(df_key):
        row = df_key.iloc[i]
        if pd.notna(row[0]) and pd.notna(row[1]):
            qid_match = re.match(r"(Q\d+)", str(row[0]).strip())
            if qid_match:
                qid = qid_match.group(1)
                text = str(row[1]).strip()

                # Look ahead to see if it has options
                has_options = False
                j = i + 1
                while j < len(df_key):
                    subrow = df_key.iloc[j]
                    if pd.isna(subrow[0]):
                        break
                    if pd.notna(subrow[1]):
                        has_options = True
                        break
                    j += 1

                if has_options:
                    question_map[qid] = text
        i += 1

    # Include only questions in both the data and the valid answer key map
    columns = sorted(data_columns.intersection(set(question_map.keys())), key=lambda q: int(q[1:]))
    question_pairs = [(qid, question_map[qid]) for qid in columns]

    return render_template('select_columns.html', filename=filename, sheet=sheet, question_pairs=question_pairs)


# -----------------------------------------
# Renders selected question results
# -----------------------------------------
@app.route('/compare_multi_questions', methods=['POST'])
def compare_multi_questions():
    filename = request.form['filename']
    sheet = request.form['sheet']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

    # Parse filters
    filter_count = int(request.form.get('filter_count', 0))
    filter_questions = []
    filter_values = []
    for i in range(filter_count):
        fq = request.form.get(f'filter_question_{i}')
        fv = request.form.get(f'filter_value_{i}', '__all__')
        if fq:
            filter_questions.append(fq)
            filter_values.append(fv)

    base_filters = {
        'filter_questions': filter_questions,
        'filter_values': filter_values,
        'sort_column': request.form.get('sort_column', '')
    }

    # Process each selected question
    questions = [
        key.replace("include_", "")
        for key in request.form.keys()
        if key.startswith("include_") and request.form.get(key)
    ]
    results = []
    for q in questions:
        types = list(dict.fromkeys(request.form.getlist(f"type_{q}")))
        for q_type in types:
            filters = deepcopy(base_filters)
            filters['cut_column'] = request.form.get(f'cut_column_{q}', '')
            filters['max_rank'] = request.form.get(f'max_rank_{q}', '')
            try:
                if q_type == 'cross_cut' and filters['cut_column']:
                    html = process_cross_cut(filepath, sheet, q, filters)
                elif q_type == 'single_choice':
                    html = process_single_choice(filepath, sheet, q, filters)
                elif q_type == 'matrix':
                    html = process_matrix_question(filepath, sheet, q, filters)
                elif q_type == 'multi_select':
                    html = process_multi_select(filepath, sheet, q, filters)
                elif q_type == 'ranked':
                    html = process_ranked_question(filepath, sheet, q, filters)
                elif q_type == 'nps':
                    html = process_nps_question(filepath, sheet, q, filters)
                else:
                    html = f"<p>Unsupported or incomplete type for {q}</p>"

                question_text = next((str(row[1]).strip() for _, row in df_key.iterrows()
                                      if str(row[0]).strip() == q and pd.notna(row[1])), None)

                results.append({'question': q, 'text': question_text, 'html': html})
            except Exception as e:
                results.append({
                    'question': q,
                    'text': f"{q} - {q_type}",
                    'html': f"<p>Error processing {q} ({q_type}): {str(e)}</p>"
                })

    results.sort(key=lambda r: int(r['question'][1:]) if r['question'].startswith('Q') else 999)

    filter_columns = list(dict.fromkeys([
        str(row[0]).strip() for _, row in df_key.iterrows()
        if pd.notna(row[0]) and re.match(r'^Q\d+$', str(row[0]).strip())
    ]))

    return render_template(
        'display_multi_results.html',
        results=results,
        filename=filename,
        sheet=sheet,
        all_columns=[r['question'] for r in results],
        filter_columns=filter_columns,
        filter_questions=filter_questions,
        filter_values=filter_values,
        sort_column=base_filters['sort_column']
    )


# -----------------------------------------
# AJAX endpoint to load filter values
# -----------------------------------------
@app.route("/get_answer_key_values", methods=["POST"])
def get_answer_key_values():
    filename = request.form.get("filename")
    question = request.form.get("question")
    if not filename or not question:
        return jsonify([])

    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

        values = []
        capture = False
        for _, row in df_key.iterrows():
            cell_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            cell_b = str(row[1]).strip() if pd.notna(row[1]) else ""

            if cell_a == question:
                capture = True
                continue
            if capture and cell_a.startswith("Q"):
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