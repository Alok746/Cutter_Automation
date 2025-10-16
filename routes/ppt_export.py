from routes.nps_question import get_nps_data
from routes.matrix_question import get_matrix_question_data

def build_nps_slide(filepath, sheet, qid, filters):
    out = get_nps_data(filepath, sheet, qid, filters)
    labels = out["col_labels"]
    promoters, neutrals, detractors = out["promoters"], out["neutrals"], out["detractors"]
    nps_scores, avg_scores = out["nps_scores"], out["average_scores"]
    question_text = out["question_text"]

    header = [None] + [{"string": label} for label in labels]
    table = [
        [{"string": "Promoters"}] + [{"number": p} for p in promoters],
        [{"string": "Neutrals"}] + [{"number": n} for n in neutrals],
        [{"string": "Detractors"}] + [{"number": d} for d in detractors],
        [{"string": "NPS"}] + [{"percentage": round(s, 3)} for s in nps_scores],
        [{"string": "Avg. Score"}] + [{"number": round(a, 2)} for a in avg_scores],
    ]

    return {
        "QuestionTextNps": [[{"string": question_text}]],
        "NpsChart": [header] + table
    }

def build_matrix_slide(filepath, sheet, qid, filters):
    out = get_matrix_question_data(filepath, sheet, qid, filters)   
    row_labels = out["row_labels"]
    col_labels = out["col_labels"]
    counts = out["count_matrix"]
    question_text = out["question_text"]

    header = [None] + [{"string": c} for c in col_labels]
    table = []
    for i, label in enumerate(row_labels):
        row = [{"string": label}] + [{"number": v} for v in counts[i]]
        table.append(row)

    return {
        "QuestionTextMatrix": [[{"string": question_text}]],
        "MatrixChart": [header] + table
    }
    
def build_single_choice_slide(filepath, sheet, qids, filters):
    from routes.single_choice import get_single_choice_data

    qid_to_question_text = {}
    qid_to_option_counts = {}
    all_options = set()

    # Step 1: Collect data
    for qid in qids:
        out = get_single_choice_data(filepath, sheet, qid, filters)
        qid_to_question_text[qid] = out["question_text"]
        summary = out["response_summary"]

        option_counts = {label: count for label, count, _ in summary}
        qid_to_option_counts[qid] = option_counts
        all_options.update(option_counts.keys())

    # Sort options and questions
    all_options = sorted(all_options)
    ordered_qids = qids  # you can sort by label if needed

    # Step 2: Build header (1 bar per question)
    header = [None]
    for qid in ordered_qids:
        col_title = "Multiple single choice" if len(qids) > 1 else qid_to_question_text[qid]
        header.append({"string": col_title})
    table = [header]

    # Step 3: Each row = option, each column = count for that qid
    for option in all_options:
        row = [{"string": option}]
        for qid in ordered_qids:
            count = qid_to_option_counts.get(qid, {}).get(option, 0)
            if count == 0:
                row.append({"string": ""})
            else:
                row.append({"number": count})
        table.append(row)

    # Step 4: Chart title
    title = qid_to_question_text[qids[0]] if len(qids) == 1 else "Multiple single choice"

    return {
        "QuestionTextSingle": [[{"string": title}]],
        "SingleChart": table
    }