from pathlib import Path
import os
from dotenv import dotenv_values, load_dotenv

chapter = Path(__file__).resolve().parent
values = dotenv_values(chapter.parent / '.env')
missing = [name for name in ('LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL_ID') if not values.get(name)]
if missing:
    raise RuntimeError('Missing root .env fields: ' + ', '.join(missing))
load_dotenv(chapter.parent / '.env', override=True)
os.environ['LLM_PROVIDER'] = 'custom'
os.environ.setdefault('SEARCH_API', 'tavily' if values.get('TAVILY_API_KEY') else 'duckduckgo')
os.environ['NOTES_WORKSPACE'] = str(chapter / '.local' / 'notes')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', app_dir=str(chapter / 'helloagents-deepresearch' / 'backend' / 'src'), host='127.0.0.1', port=8002)
