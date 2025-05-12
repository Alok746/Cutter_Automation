from flask import request, render_template
from routes.single_choice import process_single_choice
from routes.matrix_question import process_matrix_question
from routes.multiple_select import process_multi_select
from routes.cross_cut import process_cross_cut
from routes.rank_based import process_ranked_question
from routes.nps_question import process_nps_question
import os
import pandas as pd


def register_multi_question_route(app):
    @app.route('/compare_multi_questions', methods=['POST'])
    def compare_multi_questions():
        filename = request.form['filename']
        sheet = request.form['sheet']
        filepath = os.path.join('uploads', filename)

        # Read filter values if any
        filters = {
            'filter_questions': request.form.getlist('filter_question'),
            'filter_values': request.form.getlist('filter_value')
        }

        # Load the answer key to get all possible questions
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)
        questions = []
        for _, row in df_key.iterrows():
            if pd.notna(row[0]) and pd.isna(row[1]):
                questions.append(str(row[0]).strip())

        # Iterate over included questions and collect results per type
        results = []

        for q in questions:
            if not request.form.get(f"include_{q}"):
                continue

            q_type = request.form.get(f"type_{q}")
            if not q_type:
                continue

            # Dispatch to the corresponding processing function
            if q_type == 'single_choice':
                html = process_single_choice(filepath, sheet, q, filters)
            elif q_type == 'matrix':
                html = process_matrix_question(filepath, sheet, q, filters)
            elif q_type == 'multi_select':
                html = process_multi_select(filepath, sheet, q, filters)
            elif q_type == 'cross_cut':
                html = process_cross_cut(filepath, sheet, q, filters)
            elif q_type == 'ranked':
                html = process_ranked_question(filepath, sheet, q, filters)
            elif q_type == 'nps':
                html = process_nps_question(filepath, sheet, q, filters)
            else:
                html = f"<p>Unsupported type for {q}</p>"

            results.append({'question': q, 'html': html})

        # Sort results by question code (e.g. Q1, Q2, etc.)
        results.sort(key=lambda r: int(r['question'][1:]) if r['question'].startswith('Q') else 999)

        return render_template('display_multi_results.html', results=results, filename=filename, sheet=sheet)
