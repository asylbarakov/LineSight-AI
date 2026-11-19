import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from app import Handler


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_ui_and_range(self):
        with urllib.request.urlopen(self.url+'/') as response:
            body=response.read()
            self.assertIn(b'canvas', body)
        request=urllib.request.Request(self.url+'/', headers={'Range':'bytes=10-29'})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status,206)
            self.assertEqual(response.read(),body[10:30])

    def test_rejects_traversal_and_cross_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.url+'/output/../app.py')
        self.assertEqual(error.exception.code,403)
        request=urllib.request.Request(self.url+'/api/generate',data=b'{}',headers={'Origin':'https://example.com'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,403)
