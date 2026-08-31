import shutil
tools = ['tts', 'bark', 'whisper', 'faster-whisper', 'mimic', 'festival', 'flite', 'piper']
for t in tools:
    path = shutil.which(t)
    if path:
        print(f"FOUND: {t} -> {path}")
