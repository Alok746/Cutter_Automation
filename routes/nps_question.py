from flask import request, render_template
import pandas as pd
import re

def register_nps_question_routes(app):
    @app.route('/compare_nps', methods=['POST'])
    def compare_nps():
        filename = request.form['filename']
        sheet = request.form['sheet']
        column = request.form['column']
        filepath = f'uploads/{filename}'

        df = pd.read_excel(filepath, sheet_name=sheet, header=2)
        df_key = pd.read_excel(filepath, sheet_name="Answer key", header=None)

        # Extract base prefix (e.g., Q14 from 'Q14 | ABB')
        base_prefix = column.split("|")[0].strip()

        # Get all brand columns like 'Q14 | Brand'
        relevant_cols = [col for col in df.columns if col.startswith(f"{base_prefix} |")]
        col_labels = [col.split("|")[1].strip() for col in relevant_cols]

        # Multi-filter support
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

        # Hardcoded score labels: 0–10
        row_labels = [str(i) for i in range(11)]

        # Build results matrix with offset logic (score 0 counts 1s, etc.)
        result_matrix = []
        for score in row_labels:
            row = []
            value_to_count = int(score) + 1
            for col in relevant_cols:
                try:
                    count = (df[col] == value_to_count).sum()
                except:
                    count = 0
                row.append(count)
            result_matrix.append((score, row))

        # Transpose matrix to get brand-wise columns
        brand_columns = list(zip(*[row[1] for row in result_matrix]))
        col_totals = [sum(col) for col in brand_columns]

        # Promoters, Neutrals, Detractors
        promoters = [sum(col[9:11]) for col in brand_columns]
        neutrals = [sum(col[7:9]) for col in brand_columns]
        detractors = [sum(col[0:7]) for col in brand_columns]

        # NPS Score = (Promoters - Detractors) / Total
        nps_scores = []
        for i in range(len(col_totals)):
            total = col_totals[i]
            score = ((promoters[i] - detractors[i]) / total) * 100 if total > 0 else 0
            nps_scores.append(round(score, 1))

        # Average Score = sum(score * count) / total
        score_values = [int(s) for s in row_labels]
        average_scores = []
        for col in brand_columns:
            numerator = sum(score_values[i] * col[i] for i in range(len(col)))
            denominator = sum(col)
            avg = round(numerator / denominator, 2) if denominator > 0 else 0
            average_scores.append(avg)

        # Clean question codes for filter dropdown (no sponse score etc.)
        raw_ids = set()
        for col in df.columns:
            if isinstance(col, str) and re.match(r"Q\d+$", col.strip()):
                raw_ids.add(col.strip())

        all_columns = sorted(raw_ids, key=lambda x: int(x[1:]))

        return render_template(
            'results_nps.html',
            question_text=f"NPS Summary for {base_prefix}",
            row_labels=row_labels,
            col_labels=col_labels,
            result_matrix=result_matrix,
            col_totals=col_totals,
            promoters=promoters,
            neutrals=neutrals,
            detractors=detractors,
            nps_scores=nps_scores,
            average_scores=average_scores,
            filename=filename,
            sheet=sheet,
            question_code=base_prefix,
            all_columns=all_columns
        )
