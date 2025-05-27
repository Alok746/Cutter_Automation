import pandas as pd

def apply_global_filters(df: pd.DataFrame, df_key: pd.DataFrame, filters: dict) -> pd.DataFrame:
    f_questions = filters.get("filter_questions", [])
    f_values = filters.get("filter_values", [])

    for q, v in zip(f_questions, f_values):
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

        if code is not None and q in df.columns:
            df = df[df[q] == code]
    return df