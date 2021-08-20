"""Upload/serve static files."""

from pathlib import Path
from random import randint

from asgi_tools import App, ResponseRedirect, ResponseFile, Request

from .utils.templates import static as template


UPLOAD_DIR = Path(__file__).parent / 'static'
UPLOAD_FILE = UPLOAD_DIR / 'image'


app = App()


@app.route('/')
async def main(request: Request):
    """Render page."""
    salt = randint(0, 1000000)
    if request.method == 'POST':
        await request.form(upload_to=lambda name: UPLOAD_FILE)
        return ResponseRedirect(f"/?salt={salt}", status_code=302)

    return template.render(salt=salt)


@app.route('/image')
async def image(request):
    """Serve the uploaded image."""
    return ResponseFile(UPLOAD_FILE)
