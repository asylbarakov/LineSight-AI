"""Local-only HTTP UI, no web framework required."""
import base64
import json
import mimetypes
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps
from generator import generate, validate

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'output'
JOBS = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/api/jobs/'):
            job = JOBS.get(path.rsplit('/', 1)[-1])
            return self.reply(200 if job else 404, job or {'error': 'Задача не найдена'})
        if path.startswith('/output/'):
            file = (ROOT / path.lstrip('/')).resolve()
            if not file.is_relative_to(OUTPUT.resolve()):
                return self.reply(403, {'error': 'Недоступно'})
        else:
            file = ROOT/'static'/'index.html' if path == '/' else ROOT/'static'/path.lstrip('/')
            file = file.resolve()
            if not file.is_relative_to((ROOT/'static').resolve()):
                return self.reply(403, {'error': 'Недоступно'})
        if not file.is_file():
            return self.reply(404, {'error': 'Файл не найден'})
        size = file.stat().st_size
        first, last = 0, size-1
        partial = self.headers.get('Range')
        if partial:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', partial)
            if not match or not any(match.groups()):
                return self.reply(416, {'error': 'Недопустимый диапазон'})
            left, right = match.groups()
            if left:
                first = int(left)
                last = min(int(right), last) if right else last
            else:
                first = max(0, size-int(right))
            if first > last or first >= size:
                return self.reply(416, {'error': 'Диапазон вне файла'})
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(last-first+1))
        if partial:
            self.send_header('Content-Range', f'bytes {first}-{last}/{size}')
        if file.suffix == '.zip':
            self.send_header('Content-Disposition', 'attachment; filename="linesight-result.zip"')
        self.end_headers()
        with file.open('rb') as stream:
            stream.seek(first)
            remaining = last-first+1
            while remaining:
                chunk = stream.read(min(1024*1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        if self.path == '/api/import-voc':
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 3_000_000:
                    raise ValueError('XML слишком большой.')
                from annotations import parse_voc
                data = json.loads(self.rfile.read(length))
                return self.reply(200, parse_voc(data['xml'], int(data['width']), int(data['height'])))
            except Exception as exc:
                return self.reply(400, {'error': str(exc)})
        if self.path != '/api/generate':
            return self.reply(404, {'error': 'Не найдено'})
        # Local app: reject cross-origin browser submissions and bound upload size.
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8765', 'http://localhost:8765'):
            return self.reply(403, {'error': 'Недопустимый Origin'})
        if not LOCK.acquire(blocking=False):
            return self.reply(409, {'error': 'Дождитесь завершения текущей генерации.'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 70*1024*1024:
                raise ValueError('Максимальный размер запроса — 70 МБ.')
            data = json.loads(self.rfile.read(length))
            raw = base64.b64decode(data['image'].split(',', 1)[-1], validate=True)
            import io
            with Image.open(io.BytesIO(raw)) as source:
                image = ImageOps.exif_transpose(source).convert('RGB')
                if max(image.size) > 16000 or image.width*image.height > 50_000_000:
                    raise ValueError('Фото должно быть не больше 50 Мп и 16000 px по стороне.')
                config = validate(data, image.size)
                jid = uuid.uuid4().hex
                folder = OUTPUT/jid
                folder.mkdir(parents=True)
                image.save(folder/'source.png')
            JOBS[jid] = {'status': 'running', 'progress': 0,'stage':'Подготовка фото'}

            def run():
                try:
                    result = generate(folder/'source.png', config, folder,
                                      lambda p: JOBS[jid].update(progress=p),
                                      lambda text: JOBS[jid].update(stage=text))
                    JOBS[jid].update(status='done', result=result, url=f'/output/{jid}/result.zip',
                                     video_url=f'/output/{jid}/video.mp4')
                except Exception as exc:
                    JOBS[jid].update(status='error', error=str(exc))
                finally:
                    LOCK.release()

            threading.Thread(target=run, daemon=True).start()
            self.reply(202, {'job_id': jid})
        except Exception as exc:
            LOCK.release()
            self.reply(400, {'error': str(exc)})


if __name__ == '__main__':
    print('LineSight Synth: http://127.0.0.1:8765', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
