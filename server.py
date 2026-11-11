"""Local-only application server. No external packages required."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import argparse,hashlib,json,secrets,sys
from engine import Corpus,load_env,ROOT,SNAPSHOT,RETRIEVAL_VERSION
from catalog import metadata,catalog,DEPARTMENTS
from case_workbench import CaseWorkbench

APP_VERSION="1.11"
INSTANCE_ID=hashlib.sha256(str(ROOT.resolve()).casefold().encode()).hexdigest()[:20]
load_env()

def make_server(port=8765,corpus=None):
    corpus=corpus or Corpus();token=secrets.token_urlsafe(24);workbench=CaseWorkbench(corpus)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,body,ctype='application/json; charset=utf-8'):
            if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(body)
        def trusted_host(self):
            return self.headers.get('Host','') in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']
        def do_GET(self):
            if not self.trusted_host():self.send(403,{'error':'Invalid host'});return
            path=urlparse(self.path).path
            if path.startswith('/sources/labs/') and path.endswith('.html'):
                body=corpus.labs.source_html(path.rsplit('/',1)[-1][:-5])
                if body is None:self.send(404,{'error':'Chưa có nguồn xét nghiệm.'})
                else:self.send(200,body,'text/html; charset=utf-8')
                return
            # Only the source PDFs and the row/page images named in the lab bundle are served.
            lab_files=corpus.labs.served_files()
            if path in lab_files:
                file=corpus.data/path.removeprefix('/')
                if file.is_file():
                    if path.endswith('.png') and not corpus.labs.file_ok(path):
                        self.send(409,{'error':'Nguồn xét nghiệm đã thay đổi; cần đối chiếu lại.'});return
                    self.send(200,file.read_bytes(),lab_files[path]);return
            if path=='/api/health':
                import os
                self.send(200,dict(ok=True,app_id='bhyt-toan-vien',version=APP_VERSION,instance_id=INSTANCE_ID,retrieval_version=RETRIEVAL_VERSION,snapshot=SNAPSHOT,drug_entries=len({r['stt'] for r in corpus.drugs}),radio_entries=len({r['stt'] for r in corpus.radio}),chunks=len(corpus.chunks),token=token,ai_configured=bool(os.environ.get('BHYT_ENABLE_AI')=='1' and os.environ.get('OPENAI_API_KEY') and os.environ.get('OPENAI_MODEL')),embeddings=corpus.semantic_path.exists(),source_update_date=corpus.supplemental.registry['checked_as_of'],supplemental_documents=len(corpus.supplemental.documents)));return
            if path=='/api/case/drugs':
                args=parse_qs(urlparse(self.path).query)
                self.send(200,{"items":workbench.drugs(args.get("q",[""])[0][:150])});return
            if path=='/api/case/schema':
                args=parse_qs(urlparse(self.path).query)
                try:self.send(200,workbench.schema(args.get("id",[""])[0]))
                except ValueError as e:self.send(400,{"error":str(e)})
                return
            if path=='/api/metadata':
                self.send(200,metadata(corpus));return
            if path=='/api/catalog':
                args=parse_qs(urlparse(self.path).query)
                try:
                    self.send(200,catalog(corpus,args.get('q',[''])[0],args.get('group',[''])[0],args.get('appendix',[''])[0],args.get('page',['1'])[0]))
                except (ValueError,TypeError):self.send(400,{'error':'Trang tra cứu không hợp lệ.'})
                return
            local_files={'/sources/15-vbhn-byt-2024.pdf':ROOT/'data/sources/15-vbhn-byt-2024.pdf',
                         '/sources/37-2024-tt-byt.pdf':ROOT/'data/sources/37-2024-tt-byt.pdf',
                         '/fonts/geist.woff2':ROOT/'web/fonts/geist.woff2',
                         '/fonts/geist-vietnamese.woff2':ROOT/'web/fonts/geist-vietnamese.woff2'}
            local_files.update(corpus.supplemental.local_files)
            local_files['/fonts/geist-400.ttf']=ROOT/'web/fonts/geist-400.ttf'
            local_files['/fonts/geist-500.ttf']=ROOT/'web/fonts/geist-500.ttf'
            local_files['/fonts/geist-600.ttf']=ROOT/'web/fonts/geist-600.ttf'
            local_files['/fonts/geist-700.ttf']=ROOT/'web/fonts/geist-700.ttf'
            if path in local_files and local_files[path].is_file():
                self.send(200,local_files[path].read_bytes(),'application/pdf' if path.endswith('.pdf') else 'font/ttf' if path.endswith('.ttf') else 'font/woff2');return
            if path=='/api/suggest':
                q=normalize_query(parse_qs(urlparse(self.path).query).get('q',[''])[0]);names=[]
                if len(q)>=2:
                    names=[rows[0]['ingredient'] for key,rows in corpus.names.items() if q in key][:10]
                self.send(200,{'suggestions':names});return
            assets={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/case.js':'case.js'}
            if path in assets:
                file=ROOT/'web'/assets[path];ctype='text/html' if path=='/' else ('text/javascript' if path.endswith('js') else 'text/css')
                self.send(200,file.read_bytes(),ctype+'; charset=utf-8');return
            self.send(404,{'error':'Không tìm thấy.'})
        def do_POST(self):
            # Read the body before any refusal: answering while the client is still sending makes
            # Windows reset the connection, and the client then sees an abort instead of the 403.
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:length=0
            raw=self.rfile.read(min(length,20001)) if length>0 else b''
            if not self.trusted_host() or self.headers.get('X-Session-Token')!=token:self.send(403,{'error':'Phiên không hợp lệ. Tải lại trang.'});return
            if urlparse(self.path).path not in ('/api/chat','/api/case/evaluate'):self.send(404,{'error':'Không tìm thấy.'});return
            if not self.headers.get('Content-Type','').startswith('application/json'):self.send(415,{'error':'Yêu cầu JSON.'});return
            try:
                if length<1 or length>20000:self.send(413,{'error':'Nội dung quá dài.'});return
                payload=json.loads(raw)
                if urlparse(self.path).path=='/api/case/evaluate':
                    if not isinstance(payload,dict) or payload.get("department","Tất cả các khoa") not in DEPARTMENTS:raise ValueError("Khoa hoặc dữ liệu ca không hợp lệ.")
                    result=workbench.evaluate(payload);result["department"]=payload.get("department","Tất cả các khoa")
                    self.send(200,result);return
                if not isinstance(payload,dict) or not isinstance(payload.get('message'),str):raise ValueError('Câu hỏi không hợp lệ.')
                department=payload.get('department','Tất cả các khoa')
                if department not in DEPARTMENTS:raise ValueError('Khoa không hợp lệ.')
                result=corpus.converse(payload['message'],payload.get('state'),payload.get('as_of'),payload.get('confirm'))
                result['department']=department
                self.send(200,result)
            except (ValueError,TypeError,KeyError) as e:self.send(400,{'error':str(e)[:180]})
            except RecursionError:self.send(400,{'error':'Dữ liệu gửi lên lồng quá sâu.'})
            except Exception:self.send(500,{'error':'Không xử lý được yêu cầu. Thử lại hoặc kiểm tra dữ liệu nguồn.'})
    class Server(ThreadingHTTPServer):
        request_queue_size=64      # the default of 5 can refuse connections when a page loads many files at once
        daemon_threads=True
    return Server(('127.0.0.1',port),Handler)

def normalize_query(q):
    from engine import normalize
    return normalize(q[:150])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--open',action='store_true');a=p.parse_args()
    if a.open:
        try:
            from urllib.request import urlopen
            with urlopen(f'http://127.0.0.1:{a.port}/api/health',timeout=2) as response:
                running=json.load(response)
            if running.get('app_id')=='bhyt-toan-vien' and running.get('version')==APP_VERSION and running.get('instance_id')==INSTANCE_ID:
                import webbrowser
                webbrowser.open(f'http://127.0.0.1:{a.port}')
                sys.exit(0)
        except (OSError,ValueError):pass
    try:
        server=make_server(a.port);print(f'Mở http://127.0.0.1:{server.server_port} để dùng chatbot. Ctrl+C để dừng.',flush=True)
        if a.open:
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{server.server_port}')
        server.serve_forever()
    except KeyboardInterrupt:pass
    except OSError as e:print(f'Không mở được cổng {a.port}: {e}. Thử --port 8766.',file=sys.stderr);sys.exit(1)
