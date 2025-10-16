import os,re
import pickle
import pandas as pd
from typing import List
import numpy as np
import faiss

class SurveyRAG:
    def __init__(self, upload_folder: str, filename: str, raw_sheet: str, key_sheet: str = "Answer key"):
        self.filepath = os.path.join(upload_folder, filename)
        self.raw_sheet = raw_sheet
        self.key_sheet = key_sheet

        self.raw_df = None
        self.key_df = None
        self.documents = []
        self.embeddings = None
        self.index = None

    def load_excel(self):
        self.raw_df = pd.read_excel(self.filepath, sheet_name=self.raw_sheet, header=2)
        self.key_df = pd.read_excel(self.filepath, sheet_name=self.key_sheet, header=None)
        self.df = self.raw_df

    def convert_to_documents(self, max_rows=None) -> List[str]:
        docs = []

        # Step 1: Parse answer key mapping
        code_map = {}  # e.g., {'Q2': {'1': 'United States', '2': 'India'}}
        current_qid = None
        for _, row in self.key_df.iterrows():
            qid = str(row[0]).strip() if pd.notna(row[0]) else ""
            label = str(row[1]).strip() if pd.notna(row[1]) else ""

            if re.match(r"^Q\d+$", qid):
                current_qid = qid
                code_map[current_qid] = {}
            elif current_qid and qid and label:
                code_map[current_qid][str(qid)] = label

        # Step 2: Add answer key info into the context
        for qid, options in code_map.items():
            question_text = f"Question {qid}:\n"
            for code, label in options.items():
                question_text += f"- {label}: {code}\n"
            docs.append(question_text.strip())

        # Step 3: Process response rows with decoded values
        rows = self.raw_df.to_dict(orient="records") if max_rows is None else self.raw_df.head(max_rows).to_dict(orient="records")
        for i, row in enumerate(rows):
            lines = [f"Response {i+1}"]
            for col, val in row.items():
                if pd.notna(val):
                    val_str = str(int(val)) if isinstance(val, float) and val.is_integer() else str(val)
                    decoded_val = val_str

                    # Try decoding if column matches a Qx
                    if col in code_map and val_str in code_map[col]:
                        decoded_val = code_map[col][val_str] + f" ({val_str})"

                    lines.append(f"{col}: {decoded_val}")
            docs.append("\n".join(lines))

        self.documents = docs
                
        docs.insert(0, f"There are {len(self.raw_df)} total responses in this survey.")
        return docs

    def get_cache_path(self):
        base = os.path.splitext(os.path.basename(self.filepath))[0]
        os.makedirs("cache", exist_ok=True)
        return f"cache/{base}_{self.raw_sheet.replace(' ', '_')}_openai_embed.pkl"

    def load_from_cache(self):
        path = self.get_cache_path()
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.documents = data['documents']
                self.embeddings = data['embeddings']
            return True
        return False

    def save_to_cache(self):
        path = self.get_cache_path()
        with open(path, 'wb') as f:
            pickle.dump({
                'documents': self.documents,
                'embeddings': self.embeddings
            }, f)

    def embed_documents(self):
        if self.load_from_cache():
            print("✅ Loaded OpenAI embeddings from cache.")
            return self.embeddings

        if not self.documents:
            raise ValueError("❌ No documents to embed.")

        print("🔄 Getting OpenAI embeddings...")
        self.embeddings = self.get_openai_embeddings(self.documents)
        self.save_to_cache()
        return self.embeddings

    def get_openai_embeddings(self, texts: List[str], model="text-embedding-3-small") -> List[List[float]]:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        embeddings = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            response = client.embeddings.create(input=batch, model=model)
            batch_embeddings = [record.embedding for record in response.data]
            embeddings.extend(batch_embeddings)
        return embeddings

    def build_faiss_index(self):
        if self.embeddings is None:
            raise ValueError("❌ No embeddings found. Run embed_documents() first.")
        emb = np.array(self.embeddings).astype('float32')
        dim = emb.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(emb)

    def retrieve(self, query: str, top_k: None = None) -> List[str]:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.embeddings.create(
            input=[query],
            model="text-embedding-3-small"
        )
        query_vec = np.array([response.data[0].embedding]).astype('float32')
        D, I = self.index.search(query_vec, top_k)
        return [self.documents[i] for i in I[0]]
    
