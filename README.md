# TTS Project

Primary app source is in `Project Code/`.

## Run app
```bash
cd "Project Code"
source .venv/bin/activate
python app.py
```

## Seed database
```bash
cd "Project Code"
source .venv/bin/activate
python seed.py
```

## Compatibility wrappers at repo root
Root `app.py` and `seed.py` are thin wrappers that forward execution into `Project Code/`.
