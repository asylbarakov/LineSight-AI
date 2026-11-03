.PHONY: up down test reset-demo backup demo-build

up:
	docker compose up --build

down:
	docker compose down

test:
	python -m pytest
	cd frontend && npm test

# вернуть систему к состоянию «готово к показу» (очистить инспекции, загрузить готовую)
reset-demo:
	docker compose exec api python -m app.demo reset

# собрать готовую инспекцию из видео: make demo-build VIDEO=/data/demo/synth_blur.mp4
demo-build:
	docker compose exec worker python -m app.demo build $(VIDEO) "Демо-инспекция"

backup:
	./scripts/backup.sh
