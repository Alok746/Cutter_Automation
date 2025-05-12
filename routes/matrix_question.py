from flask import request, render_template
import pandas as pd
import re

def register_matrix_question_routes(app):
    @app.route('/compare_matrix_question', methods=['POST'])
    def compare_matrix_question():
        filename = request.form['filename']
        sheet = request.form['sheet']
        column = request.form['column']
        filepath = f'uploads/{filename}'

        df = pd.read_excel(filepath, sheet_name=sheet, header=2)
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

        # Multi-filter logic
        filter_questions = request.form.getlist("filter_question")
        filter_values = request.form.getlist("filter_value")

        if filter_questions and filter_values:
            for q, v in zip(filter_questions, filter_values):
                if v == "__all__" or not q:
                    continue
                filter_code = None
                capture = False
                for _, row in df_key.iterrows():
                    if pd.notna(row[0]) and str(row[0]).strip() == q:
                        capture = True
                        continue
                    if capture and pd.isna(row[0]):
                        break
                    if capture and pd.notna(row[1]):
                        if str(row[1]).strip() == v:
                            filter_code = row[0]
                            break
                df = df[df[q] == filter_code] if filter_code is not None else df[0:0]

        base_prefix = column.split(":")[0].strip()
        relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

        # Extract response options (row labels)
        option_map = {}
        capture = False
        question_text = base_prefix
        for _, row in df_key.iterrows():
            if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
                capture = True
                continue
            if capture and pd.isna(row[0]):
                break
            if capture and pd.notna(row[0]) and pd.notna(row[1]):
                try:
                    key = str(int(float(row[0]))).strip()
                    value = str(row[1]).strip()
                    option_map[key] = value
                except:
                    continue

        row_labels = list(option_map.values())
        col_labels = [col.split(":")[1].strip() for col in relevant_cols]

        # Create matrices
        count_matrix = []
        percent_matrix = []
        col_totals = []

        # Compute column totals (respondents per sub-question)
        for col in relevant_cols:
            col_totals.append(df[col].notna().sum())

        # Count and percent matrices
        for code, label in option_map.items():
            row_counts = []
            row_percents = []
            for i, col in enumerate(relevant_cols):
                count = (df[col].dropna().astype(str).str.strip() == code).sum()
                row_counts.append(count)
                percent = (count / col_totals[i]) * 100 if col_totals[i] > 0 else 0
                row_percents.append(percent)
            count_matrix.append(row_counts)
            percent_matrix.append(row_percents)

        # Sorting question IDs
        raw_question_ids = set()
        for col in df.columns:
            match = re.search(r"(Q\d+)", col)
            raw_question_ids.add(match.group(1) if match else col.strip())

        def question_sort_key(q):
            match = re.match(r"Q(\d+)", q)
            return (0, int(match.group(1))) if match else (1, q.lower())

        all_columns = sorted(raw_question_ids, key=question_sort_key)

        return render_template(
            'results_matrix.html',
            question_text=question_text,
            row_labels=row_labels,
            col_labels=col_labels,
            count_matrix=count_matrix,
            percent_matrix=percent_matrix,
            col_totals=col_totals,
            filename=filename,
            sheet=sheet,
            question_code=base_prefix,
            all_columns=all_columns
        )
