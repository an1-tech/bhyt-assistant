"""Explicit opt-in semantic indexing; calls the paid embedding API only when run.
Usage: python tools/build_embeddings.py. Interrupted builds resume per document.
"""
import sys,os,json,math,sqlite3,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Corpus,load_env,api_post
load_env()
if not os.environ.get('OPENAI_API_KEY') or not os.environ.get('OPENAI_EMBEDDING_MODEL'):
    raise SystemExit('Cấu hình OPENAI_API_KEY và OPENAI_EMBEDDING_MODEL trong .env trước.')
c=Corpus();model=os.environ['OPENAI_EMBEDDING_MODEL'];db=sqlite3.connect(c.semantic_path)
db.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)')
db.execute('CREATE TABLE IF NOT EXISTS vectors(chunk_id TEXT PRIMARY KEY,vector TEXT)')
old=dict(db.execute('select key,value from metadata'))
if old and (old.get('corpus_sha256')!=c.fingerprint or old.get('model')!=model):
    db.close();raise SystemExit('Chỉ mục thuộc phiên bản dữ liệu/model khác. Đổi tên data/embeddings.sqlite để tạo phiên bản mới.')
db.executemany('INSERT OR REPLACE INTO metadata VALUES(?,?)',[('corpus_sha256',c.fingerprint),('model',model),('complete','false')]);db.commit()
done={x[0] for x in db.execute('select chunk_id from vectors')};pending=[x for x in c.chunks if x['id'] not in done]
print(f'Sẽ gửi {len(pending)} đoạn văn bản pháp luật công khai để tạo embedding. API có thể tính phí. Ctrl+C để dừng.',flush=True)
for start in range(0,len(pending),16):
    batch=pending[start:start+16]
    result=api_post('embeddings',{'model':model,'input':[x['text'][:6000] for x in batch]})
    rows=sorted(result['data'],key=lambda x:x['index'])
    if len(rows)!=len(batch) or [r['index'] for r in rows]!=list(range(len(batch))):raise ValueError('Embedding response incomplete')
    for chunk,row in zip(batch,rows):
        vector=row['embedding'];mag=math.sqrt(sum(x*x for x in vector)) or 1
        db.execute('INSERT OR REPLACE INTO vectors VALUES(?,?)',(chunk['id'],json.dumps([v/mag for v in vector])))
    db.commit();print(f'Đã xử lý {min(start+len(batch),len(pending))}/{len(pending)} đoạn mới',flush=True)
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('complete','true'));db.commit()
db.close();print('Hoàn tất. Khởi động lại server để dùng chỉ mục vector.')
