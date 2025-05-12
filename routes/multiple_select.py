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

        base_prefix = column.split(":")[0].strip()
        relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

        # Filter logic
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

        total_respondents = df[relevant_cols[0]].notna().sum() if relevant_cols else 0
        response_summary = []
        total_responses = 0

        for label in answer_labels:
            col_match = next((col for col in relevant_cols if label in col), None)
            count = (df[col_match] == 1).sum() if col_match else 0
            total_responses += count
            response_summary.append((label, count))

        final_data = []
        percent_respondents = []
        percent_responses = []

        for label, count in response_summary:
            pct_respndt = (count / total_respondents * 100) if total_respondents else 0
            pct_respns = (count / total_responses * 100) if total_responses else 0
            final_data.append((label, count, pct_respndt, pct_respns))
            percent_respondents.append(pct_respndt)
            percent_responses.append(pct_respns)

        # Sorting logic
        sort_order = request.form.get("sort_order", "none")
        sort_column = request.form.get("sort_column", "")

        column_map = {
            "% of respondents": 2,
            "% of responses": 3
        }

        if sort_order in ("asc", "desc") and sort_column in column_map:
            idx = column_map[sort_column]
            reverse = sort_order == "desc"
            final_data = sorted(final_data, key=lambda x: x[idx], reverse=reverse)

        sort_column_options = list(column_map.keys())

        # All clean column names for filter dropdown
        raw_qids = set()
        for col in df.columns:
            if isinstance(col, str) and re.match(r"Q\d+$", col.strip()):
                raw_qids.add(col.strip())

        all_columns = sorted(raw_qids, key=lambda x: int(x[1:]))

        return render_template(
            'results_multiple_select.html',
            question_text=question_text,
            response_summary=final_data,
            total_responses=total_responses,
            total_respondents=total_respondents,
            total_pct_response=sum(x[3] for x in final_data),
            total_pct_respondent=sum(x[2] for x in final_data),
            min_pct=min(percent_responses) if percent_responses else 0,
            max_pct=max(percent_responses) if percent_responses else 0,
            sort_order=sort_order,
            sort_column=sort_column,
            sort_column_options=sort_column_options,
            filename=filename,
            sheet=sheet,
            question_code=base_prefix,
            all_columns=all_columns
        )
