from flask import request, render_template
import pandas as pd
import re

def register_multiple_select_routes(app):
    @app.route('/compare_multiple_select', methods=['POST'])
    def compare_multiple_select():
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

        answer_labels = []
        capture = False
        question_text = base_prefix
        for _, row in df_key.iterrows():
            if pd.notna(row[0]) and str(row[0]).strip() == base_prefix:
                capture = True
                if pd.notna(row[1]):
                    question_text = f"{base_prefix}: {str(row[1]).strip()}"
                continue
            if capture and pd.isna(row[0]):
                break
            if capture and pd.notna(row[1]):
                answer_labels.append(str(row[1]).strip())

        total_respondents = len(df)

        response_summary = []
        total_responses = 0
        for label in answer_labels:
            match_col = next((col for col in relevant_cols if label in col), None)
            if match_col:
                count = (df[match_col] == 1).sum()
                total_responses += count
                response_summary.append((label, count))
            else:
                response_summary.append((label, 0))

        response_summary_pct = []
        percent_responses = []

        for label, count in response_summary:
            pct_response = (count / total_responses) * 100 if total_responses > 0 else 0
            pct_respondent = (count / total_respondents) * 100 if total_respondents > 0 else 0
            response_summary_pct.append((label, count, pct_respondent, pct_response))
            percent_responses.append(pct_response)

        min_pct = min(percent_responses) if percent_responses else 0
        max_pct = max(percent_responses) if percent_responses else 0
        total_pct_response = sum(percent_responses)
        total_pct_respondent = sum(pct_respondent for _, _, pct_respondent, _ in response_summary_pct)

        raw_question_ids = set()
        for col in df.columns:
            match = re.search(r"(Q\d+)", col)
            raw_question_ids.add(match.group(1) if match else col.strip())

        def question_sort_key(q):
            match = re.match(r"Q(\d+)", q)
            return (0, int(match.group(1))) if match else (1, q.lower())

        all_columns = sorted(raw_question_ids, key=question_sort_key)

        return render_template(
            'results_multiple_select.html',
            question_text=question_text,
            response_summary=response_summary_pct,
            total_responses=total_responses,
            total_respondents=total_respondents,
            total_pct_response=total_pct_response,
            total_pct_respondent=total_pct_respondent,
            min_pct=min_pct,
            max_pct=max_pct,
            filename=filename,
            sheet=sheet,
            question_code=base_prefix,
            all_columns=all_columns
        )
