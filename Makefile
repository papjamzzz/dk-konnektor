.PHONY: setup run push zip

setup:
	python3 -m pip install -r requirements.txt
	cp -n .env.example .env 2>/dev/null || true
	mkdir -p static templates data

run:
	python3 app.py

push:
	git add -A
	git commit -m "update dk-konnektor"
	git push origin main

zip:
	zip -r dk-konnektor.zip . \
	  --exclude "*.pyc" \
	  --exclude "__pycache__/*" \
	  --exclude ".env" \
	  --exclude "data/*" \
	  --exclude ".git/*"
