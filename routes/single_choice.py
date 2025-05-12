from flask import request, render_template
import pandas as pd
from collections import Counter
import re

def register_single_choice_routes(app):
    @app.route('/compare_answers', methods=['POST'])
    def compare_answers():
        filename = request.form['filename']
        sheet = request.form['sheet']
        column = request.form['column']
        filepath = f'uploads/{filename}'

        df = pd.read_excel(filepath, sheet_name=sheet, header=2)
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

        # Multi-filter
        filter_questions = request.form.getlist("filter_question")
        filter_values = request.form.getlist("filter_value")
        if filter_questions and filter_values:
            for q, v in zip(filter_questions, filter_values):
                if v == "__all__" or not q:
                    continue
                code = None
                capture = False
                for _, row in df_key.iterrows():
                    if pd.notna(row[0]) and str(row[0]).strip() == q:
                        capture = True
                        continue
                    if capture and pd.isna(row[0]):
                        break
                    if capture and pd.notna(row[1]):
                        if str(row[1]).strip() == v:
                            code = row[0]
                            break
                df = df[df[q] == code] if code is not None else df[0:0]

        selected_values = df[column].dropna()

        # Mapping
        mapping_dict = {}
        capture = False
        question_text = column
        for _, row in df_key.iterrows():
            if pd.notna(row[0]) and str(row[0]).strip() == column:
                capture = True
                if pd.notna(row[1]):
                    question_text = f"{column}: {str(row[1]).strip()}"
                continue
            if capture and pd.isna(row[0]):
                break
            if capture and pd.notna(row[0]) and pd.notna(row[1]):
                try:
                    key = str(int(float(row[0]))).strip()
                    value = str(row[1]).strip()
                    mapping_dict[key] = value
                except:
                    continue

        def normalize(val):
            try:
                return mapping_dict.get(str(int(float(val))).strip(), "Unknown")
            except:
                return "Unknown"

        mapped_values = selected_values.apply(normalize)
        actual_counts = Counter(mapped_values)
        total_count = sum(actual_counts.values())

        original_order = list(mapping_dict.values())
        response_summary = []
        for label in original_order:
            count = actual_counts.get(label, 0)
            pct = (count / total_count * 100) if total_count else 0
            response_summary.append((label, count, pct))

        # Sort logic
        sort_order = request.form.get("sort_order", "none")
        if sort_order == "asc":
            response_summary = sorted(response_summary, key=lambda x: x[2])
        elif sort_order == "desc":
            response_summary = sorted(response_summary, key=lambda x: x[2], reverse=True)

        # Total % (can go over 100% only in data errors, but include it)
        total_pct = sum(x[2] for x in response_summary)

        # Filter column list
        raw_ids = set()
        for col in df.columns:
            match = re.search(r"(Q\d+)", col)
            raw_ids.add(match.group(1) if match else col.strip())

        def question_sort_key(q):
            match = re.match(r"Q(\d+)", q)
            return (0, int(match.group(1))) if match else (1, q.lower())

        all_columns = sorted(raw_ids, key=question_sort_key)

        return render_template(
            'results.html',
            question_text=question_text,
            response_summary=response_summary,
            total_count=total_count,
            total_pct=total_pct,
            min_pct=min(x[2] for x in response_summary),
            max_pct=max(x[2] for x in response_summary),
            sort_order=sort_order,
            filename=filename,
            sheet=sheet,
            question_code=column,
            all_columns=all_columns,
            sort_column_options = []
        )
