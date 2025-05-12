from flask import request, render_template
import pandas as pd
import re

def register_cross_cut_routes(app):
    @app.route('/compare_cross_cut', methods=['POST'])
    def compare_cross_cut():
        filename = request.form['filename']
        sheet = request.form['sheet']
        base_col = request.form['column']
        cut_col = request.form.get("cut_column")
        filepath = f'uploads/{filename}'

        df = pd.read_excel(filepath, sheet_name=sheet, header=2)
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

        # Apply filters
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

        base_prefix = base_col.split(":")[0].strip()
        cut_prefix = cut_col.split(":")[0].strip()
        relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

        # Get base options
        base_options = []
        capture = False
        for _, row in df_key.iterrows():
            if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
                capture = True
                continue
            if capture and pd.isna(row[0]):
                break
            if capture and pd.notna(row[1]):
                base_options.append(str(row[1]).strip())

        # Get cut value map
        cut_value_map = {}
        capture = False
        for _, row in df_key.iterrows():
            if pd.notna(row[0]) and str(row[0]).strip() == cut_prefix:
                capture = True
                continue
            if capture and pd.isna(row[0]):
                break
            if capture and pd.notna(row[0]) and pd.notna(row[1]):
                cut_value_map[row[0]] = str(row[1]).strip()

        cut_codes = list(cut_value_map.keys())
        cut_labels = list(cut_value_map.values())

        # Total respondents (cut_col not null)
        total_respondents = df[cut_col].notna().sum() if cut_col else 0

        # Column totals from cut column
        cut_totals = [df[df[cut_col] == code].shape[0] for code in cut_codes]

        # Count matrix
        result_matrix = []
        for base_option in base_options:
            row_counts = []
            match_col = next((col for col in relevant_cols if base_option in col), None)
            if match_col:
                for cut_val in cut_codes:
                    filtered = df[df[cut_col] == cut_val]
                    count = filtered[match_col].notna().sum()
                    row_counts.append(count)
            else:
                row_counts = [0] * len(cut_codes)
            row_total = sum(row_counts)
            result_matrix.append((base_option, row_total, row_counts))

        # Percentage matrix
        percent_matrix = []
        for label, row_total, row_counts in result_matrix:
            row_percents = [
                (v / cut_totals[i] * 100) if cut_totals[i] > 0 else 0
                for i, v in enumerate(row_counts)
            ]
            overall_pct = (row_total / total_respondents * 100) if total_respondents > 0 else 0
            percent_matrix.append((label, overall_pct, row_percents))

        # Sidebar column sort
        raw_question_ids = set()
        for col in df.columns:
            match = re.search(r"(Q\d+)", col)
            raw_question_ids.add(match.group(1) if match else col.strip())

        def question_sort_key(q):
            match = re.match(r"Q(\d+)", q)
            return (0, int(match.group(1))) if match else (1, q.lower())

        all_columns = sorted(raw_question_ids, key=question_sort_key)

        return render_template(
            'results_cross_cut.html',
            question_text=f"{base_prefix} x {cut_prefix}",
            cut_headers=cut_labels,
            result_matrix=result_matrix,
            percent_matrix=percent_matrix,
            total_respondents=total_respondents,
            cut_totals=cut_totals,
            filename=filename,
            sheet=sheet,
            question_code=base_prefix,
            cut_column=cut_prefix,
            all_columns=all_columns
        )
