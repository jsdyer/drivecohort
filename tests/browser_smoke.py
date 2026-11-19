"""Drive lookup, source-backed quarters, local-file privacy and mobile at a project subpath."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

def report(temp):
    doc=dict(json_format_version=[1,0],model_name='ST12000NM0007',serial_number='SERIAL-ONLY-IN-READER',temperature={'current':temp})
    return {'name':'disk.json','mimeType':'application/json','buffer':json.dumps(doc).encode()}

def main():
    screenshots=ROOT/'browser-checks'
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        shutil.copytree(ROOT/'dist',Path(directory)/'drivecohort')
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=directory))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or None)
                page=browser.new_page(viewport={'width':1280,'height':960})
                errors=[]
                page.on('pageerror',lambda e: errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/drivecohort/')
                expect(page.locator('#modelname')).to_have_text('ST12000NM0007')
                page.locator('#quarter').select_option('2025-Q2')
                expect(page.locator('#afr')).to_have_text('3.58%')
                expect(page.locator('#days')).to_have_text('91,801')
                expect(page.locator('#drives')).to_have_text('1,014')
                expect(page.locator('#failures')).to_have_text('9')
                assert page.locator('#rowSource a').get_attribute('href').startswith('https://www.backblaze.com/')
                page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
                page.locator('#search').fill('MG08ACA16TEY')
                page.locator('#search').press('Enter')
                expect(page.locator('#modelname')).to_have_text('MG08ACA16TEY')
                page.locator('#search').fill('<unknown>')
                page.locator('#search').press('Enter')
                expect(page.locator('#empty')).to_contain_text('No matching cohort')
                requests=[]
                page.on('request',lambda r:requests.append(r.url))
                page.locator('#file0').set_input_files(report(33))
                page.locator('#file1').set_input_files(report(35))
                expect(page.locator('#reportTable')).to_contain_text('+2 °C')
                expect(page.locator('#reportMsg')).to_contain_text('identity matches locally')
                assert 'SERIAL-ONLY-IN-READER' not in page.locator('body').inner_text()
                assert not requests,requests
                page.locator('#clear').click()
                expect(page.locator('#reportTable')).to_be_empty()
                page.set_viewport_size({'width':360,'height':780})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown()
if __name__=='__main__': main()
