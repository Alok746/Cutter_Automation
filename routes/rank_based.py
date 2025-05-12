from flask import request, render_template
import pandas as pd
import re

def register_ranked_question_routes(app):
    @app.route('/compare_ranked', methods=['POST'])
    def compare_ranked():
        filename = request.form['filename']
        sheet = request.form['sheet']
        column = request.form['column']
        max_rank_input = request.form.get("max_rank")
        sort_order = request.form.get("sort_order", "none")
        sort_column = request.form.get("sort_column", "Overall")
        filepath = f'uploads/{filename}'

        df = pd.read_excel(filepath, sheet_name=sheet, header=2)
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

        raw_question_ids = set()
        for col in df.columns:
            match = re.search(r"(Q\d+)", col)
            raw_question_ids.add(match.group(1) if match else col.strip())

        def question_sort_key(q):
            match = re.match(r"Q(\d+)", q)
            return (0, int(match.group(1))) if match else (1, q.lower())

        all_columns = sorted(raw_question_ids, key=question_sort_key)

        # Apply filters
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

        base_prefix = column.split(":")[0].strip()
        relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix}:")]

        actual_max = 0
        for col in relevant_cols:
            try:
                col_max = pd.to_numeric(df[col], errors='coerce').max()
                if pd.notna(col_max) and col_max > actual_max:
                    actual_max = int(col_max)
            except:
                continue

        try:
            max_rank = int(max_rank_input)
            if max_rank > actual_max:
                max_rank = actual_max
        except (TypeError, ValueError):
            max_rank = actual_max

        rank_labels = [f"Rank {i}" for i in range(1, max_rank + 1)]

        # Total respondents (at least one ranked)
        total_respondents = df[relevant_cols].notna().any(axis=1).sum()

        result_matrix = []
        col_totals = [0] * max_rank

        for col in relevant_cols:
            label = col.split(":")[1].strip() if ":" in col else col
            counts = []
            for i in range(1, max_rank + 1):
                count = (df[col] == i).sum()
                counts.append(count)
                col_totals[i - 1] += count
            row_total = sum(counts)
            result_matrix.append((label, row_total, counts))

        percent_matrix = []
        for label, row_total, counts in result_matrix:
            rank_percents = [(count / row_total * 100 if row_total > 0 else 0) for count in counts]
            overall_pct = (row_total / total_respondents * 100) if total_respondents > 0 else 0
            percent_matrix.append((label, overall_pct, rank_percents))

        # Sort logic
        column_names = ["Overall"] + rank_labels
        if sort_order in ("asc", "desc") and sort_column in column_names:
            idx = column_names.index(sort_column)
            reverse = sort_order == "desc"
            zipped = list(zip(percent_matrix, result_matrix))
            zipped.sort(key=lambda x: x[0][1] if idx == 0 else x[0][2][idx - 1], reverse=reverse)
            percent_matrix, result_matrix = zip(*zipped)
            percent_matrix = list(percent_matrix)
            result_matrix = list(result_matrix)

        return render_template(
            'results_ranked.html',
            question_text=f"Ranked Summary for {base_prefix}",
            rank_labels=rank_labels,
            result_matrix=result_matrix,
            percent_matrix=percent_matrix,
            col_totals=col_totals,
            overall_total=total_respondents,
            total_respondents=total_respondents,
            sort_order=sort_order,
            sort_column=sort_column,
            sort_column_options=column_names,
            filename=filename,
            sheet=sheet,
            question_code=base_prefix,
            all_columns=all_columns
        )
